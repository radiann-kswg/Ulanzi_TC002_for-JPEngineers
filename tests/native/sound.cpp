#include "../../firmware/clock.h"
#include <cassert>
#include <set>

int main() {
    using namespace tc;
    Clock clock;
    std::set<std::string> files{"/res/ui/audio/Enter.mp3", "/tmp/ui/audio/Rotate.mp3",
        "/tmp/ui/audio/Btn.mp3", "/tmp/ui/tc002/button.mp3", "/res/ui/audio/Clock.mp3"};
    auto path=[&](Sound cue) {
        return soundPath(cue, [](const std::string& rel) { return "/tmp/ui/"+rel; },
                        [&](const std::string& file) { return files.count(file)!=0; });
    };
    assert(path(clock.command(Action::Knob,0))=="/res/ui/audio/Enter.mp3");
    assert(path(clock.command(Action::Next,50))=="/tmp/ui/audio/Rotate.mp3");
    assert(path(clock.command(Action::HoldKnob,100))=="/res/ui/audio/Enter.mp3");
    assert(path(clock.command(Action::Next,150))=="/tmp/ui/audio/Rotate.mp3");
    assert(path(clock.command(Action::Minus,200))=="/tmp/ui/audio/Btn.mp3");
    files.erase("/tmp/ui/audio/Btn.mp3");
    assert(path(Sound::Button)=="/tmp/ui/tc002/button.mp3");
    files.erase("/tmp/ui/audio/Rotate.mp3");
    files.insert("/res/ui/audio/Rotate.wav");
    assert(path(Sound::Rotate)=="/res/ui/audio/Rotate.wav");
    assert(path(Sound::RestTick)=="/res/ui/audio/Clock.mp3");
    for (auto cue : {Sound::RestTick, Sound::StopwatchTick, Sound::Alarm}) {
        auto stock=std::string("/tmp/ui/audio/")+soundAsset(cue).stock;
        files.insert(stock);
        assert(path(cue)==stock);
    }
    assert(path(Sound::Minute).empty());
    files.insert("/tmp/ui/tc002/minute.wav");
    assert(path(Sound::Minute)=="/tmp/ui/tc002/minute.wav");
    assert(preferSound(Sound::Enter,Sound::None)==Sound::Enter);
    assert(preferSound(Sound::Minute,Sound::Enter)==Sound::Enter);
    assert(preferSound(Sound::Rest,Sound::Button)==Sound::Rest);
    assert(preferSound(Sound::Resume,Sound::Alarm)==Sound::Alarm);
    assert(preferSound(Sound::Silence,Sound::Rotate)==Sound::Silence);
    assert(!canInterrupt(Sound::Rotate,Sound::Rotate));
    assert(canInterrupt(Sound::Rotate,Sound::Enter));
    assert(!canInterrupt(Sound::Enter,Sound::Tick));
    assert(!canInterrupt(Sound::Rest,Sound::Enter));
    for (auto name : {"noon", "midnight", "notification"})
        files.insert(std::string("/tmp/ui/tc002/")+name+".mp3");
    assert(path(Sound::Noon)=="/tmp/ui/tc002/noon.mp3" && path(Sound::TimerExpired)==path(Sound::Noon));
    assert(path(Sound::PomodoroResume)==path(Sound::Noon));
    assert(path(Sound::Midnight)=="/tmp/ui/tc002/midnight.mp3" && path(Sound::PomodoroRest)==path(Sound::Midnight));
    assert(path(Sound::Notification)=="/tmp/ui/tc002/notification.mp3");
    assert(!canInterrupt(Sound::TimerExpired,Sound::Alarm) && canInterrupt(Sound::TimerExpired,Sound::Silence));
    assert(!canInterrupt(Sound::PomodoroRest,Sound::RestTick));
}
