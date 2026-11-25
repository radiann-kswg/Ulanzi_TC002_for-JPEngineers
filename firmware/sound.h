#pragma once
#include <string>

namespace tc {
enum class Sound { None, Tick, RestTick, StopwatchTick, Minute, Hour, Midnight, Rest,
                   Resume, Alarm, Rotate, Enter, Button, Silence };

enum class SoundPriority { Quiet, Beat, Chime, Control, Phase, Alert, Stop };
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
    case Sound::Hour:          return {nullptr, "hour", P::Chime};
    case Sound::Midnight:      return {nullptr, "midnight", P::Chime};
    case Sound::Rest:          return {nullptr, "rest", P::Phase};
    case Sound::Resume:        return {nullptr, "resume", P::Phase};
    case Sound::Alarm:         return {"Tip.mp3", "alarm", P::Alert};
    case Sound::Silence:       return {nullptr, nullptr, P::Stop};
    case Sound::None:          break;
    }
    return {nullptr, nullptr, P::Quiet};
}

inline Sound preferSound(Sound first, Sound next) {
    return soundAsset(next).priority >= soundAsset(first).priority ? next : first;
}

inline bool canInterrupt(Sound playing, Sound next) {
    auto priority = soundAsset(next).priority;
    if (priority == SoundPriority::Beat || (playing == Sound::Rotate && next == Sound::Rotate))
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
