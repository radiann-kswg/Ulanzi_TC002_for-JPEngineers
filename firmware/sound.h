#pragma once
#include <atomic>
#include <cstdint>
#include <string>

namespace tc {
enum class Sound { None, Tick, RestTick, StopwatchTick, Minute,
                   Hour1, Hour2, Hour3, Hour4, Hour5, Hour6, Hour7, Hour8, Hour9, Hour10, Hour11,
                   Hour18, Hour19, Hour20, Hour21, Hour22, Hour23, Noon, Midnight,
                   Notification, Rest, PomodoroRest, Resume, PomodoroResume, TimerExpired, Alarm,
                   Rotate, Enter, Button, Silence };

// The first five hours of either half-day share a recording.
inline Sound hourSound(int hour) {
    if (hour==0) return Sound::Midnight;
    if (hour==12) return Sound::Noon;
    if (hour>=18) return Sound(int(Sound::Hour18)+hour-18);
    return Sound(int(Sound::Hour1)+hour%12-1);
}

enum class SoundPriority { Quiet, Beat, Chime, Control, Notice, Hourly, Phase, Alert, Stop };
struct SoundAsset {
    const char* stock;
    const char* fallback;
    SoundPriority priority;
};

inline SoundAsset soundAsset(Sound cue) {
    using P = SoundPriority;
    switch (cue) {
    case Sound::Tick:          return {"Clock.mp3", "tick", P::Beat};
    case Sound::RestTick:      return {"SlowClock.mp3", "tick", P::Beat};
    case Sound::StopwatchTick: return {"StopWatch.mp3", "tick", P::Beat};
    case Sound::Rotate:        return {"Rotate.mp3", "rotate", P::Control};
    case Sound::Button:        return {"Btn.mp3", "button", P::Control};
    case Sound::Enter:         return {"Enter.mp3", "enter", P::Control};
    case Sound::Minute:        return {nullptr, "minute", P::Chime};
    case Sound::Hour1: case Sound::Hour2: case Sound::Hour3: case Sound::Hour4:
    case Sound::Hour5: case Sound::Hour6: case Sound::Hour7: case Sound::Hour8:
    case Sound::Hour9: case Sound::Hour10: case Sound::Hour11:
    case Sound::Hour18: case Sound::Hour19: case Sound::Hour20:
    case Sound::Hour21: case Sound::Hour22: case Sound::Hour23: {
        static const char* const names[]={
            "hour01", "hour02", "hour03", "hour04", "hour05", "hour06", "hour07", "hour08",
            "hour09", "hour10", "hour11",
            "hour18", "hour19", "hour20", "hour21", "hour22", "hour23"};
        return {nullptr, names[int(cue)-int(Sound::Hour1)], P::Hourly};
    }
    case Sound::Noon:          return {nullptr, "noon", P::Hourly};
    case Sound::Midnight:      return {nullptr, "midnight", P::Hourly};
    case Sound::Notification:  return {nullptr, "notification", P::Notice};
    case Sound::Rest:          return {nullptr, "rest", P::Phase};
    case Sound::PomodoroRest:  return {nullptr, "midnight", P::Phase};
    case Sound::Resume:        return {nullptr, "resume", P::Phase};
    case Sound::PomodoroResume:return {nullptr, "noon", P::Phase};
    case Sound::TimerExpired:  return {nullptr, "noon", P::Alert};
    case Sound::Alarm:         return {"Tip.mp3", "alarm", P::Alert};
    case Sound::Silence:       return {nullptr, nullptr, P::Stop};
    case Sound::None:          break;
    }
    return {nullptr, nullptr, P::Quiet};
}

// An hourly melody keeps the effect player busy until it really ends. The SDK can report
// the player idle before it dispatches the MP3's completion. Starting the melody can also
// stop a shorter sound whose completion then arrives through the melody's newly registered
// callback. Every hourly clip rings for about 1.75 s, so an end reported within the first
// second belongs to the sound the melody replaced.
class HourlyHold {
    std::atomic<bool> active{false};
    std::atomic<int64_t> startedAt{0};
public:
    static constexpr int64_t earliestEnd=1000, latestEnd=2000;
    void start(bool hourly, int64_t now) { startedAt=now; active=hourly; }
    void release() { active=false; }
    // Called from the player's completion and error callbacks.
    void ended(int64_t now) { if (now-startedAt.load()>=earliestEnd) active=false; }
    bool holds(int64_t now) const { return active.load() && now-startedAt.load()<latestEnd; }
};

inline Sound preferSound(Sound first, Sound next) {
    return soundAsset(next).priority >= soundAsset(first).priority ? next : first;
}

inline bool canInterrupt(Sound playing, Sound next) {
    auto priority = soundAsset(next).priority;
    if (priority == SoundPriority::Beat || (playing == Sound::Rotate && next == Sound::Rotate) ||
        (playing == Sound::TimerExpired && next == Sound::Alarm))
        return false;
    return priority >= soundAsset(playing).priority;
}

// A trial has its own resource root and can still use the installed clock's originals.
template<class ResourcePath, class Readable>
std::string soundPath(Sound cue, ResourcePath resource, Readable readable) {
    auto asset = soundAsset(cue);
    if (!asset.fallback) return {};
    auto stockPath = [&](const char* file) -> std::string {
        std::string rel = std::string("audio/") + file;
        std::string local = resource(rel);
        if (readable(local)) return local;
        std::string resident = "/res/ui/" + rel;
        return resident != local && readable(resident) ? resident : std::string();
    };
    if (asset.stock) {
        auto path = stockPath(asset.stock);
        if (path.empty() && cue == Sound::Rotate) path = stockPath("Rotate.wav");
        if (path.empty() && (cue == Sound::RestTick || cue == Sound::StopwatchTick))
            path = stockPath("Clock.mp3");
        if (!path.empty()) return path;
    }
    std::string stem = std::string("tc002/") + asset.fallback;
    for (auto ext : {".mp3", ".wav"}) {
        auto path = resource(stem + ext);
        if (readable(path)) return path;
    }
    return {};
}
}
