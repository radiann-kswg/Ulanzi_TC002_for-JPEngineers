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
    files.insert("/tmp/ui/tc002/hour11.mp3");
    files.insert("/tmp/ui/tc002/hour23.mp3");
    assert(hourSound(1)==Sound::Hour1 && hourSound(11)==Sound::Hour11);
    assert(hourSound(13)==Sound::Hour1 && hourSound(17)==Sound::Hour5);
    assert(hourSound(18)==Sound::Hour18 && hourSound(23)==Sound::Hour23);
    assert(path(Sound::Hour11)=="/tmp/ui/tc002/hour11.mp3" && path(Sound::Hour23)=="/tmp/ui/tc002/hour23.mp3");
    assert(path(Sound::Hour1).empty());
    HourlyHold hold;
    uint32_t play=hold.start(true,10000);
    assert(hold.holds(10000));
    hold.ended(play,10030);  // The completion of the button sound the melody stopped.
    assert(hold.holds(11700));
    hold.ended(play,11760);  // The melody's own completion.
    assert(!hold.holds(11760));
    const uint32_t earlier=hold.start(true,12000);
    play=hold.start(true,12060);  // Silence, then the next melody.
    hold.ended(earlier,13210);  // A late callback from the earlier melody.
    assert(hold.holds(13210));
    hold.ended(play,13990);
    assert(!hold.holds(13990));
    hold.start(true,20000);  // A lost completion releases the player at the deadline.
    assert(hold.holds(21999) && !hold.holds(22000));
    hold.start(true,30000);
    hold.release();
    assert(!hold.holds(30000));
    hold.start(true,40000);
    hold.start(false,40500);  // An alarm replaces the melody.
    assert(!hold.holds(40500));
    const int64_t wrap=int64_t(1)<<32;  // The 32-bit start time wraps after 49.7 days.
    play=hold.start(true,wrap-300);
    hold.ended(play,wrap-270);
    assert(hold.holds(wrap+1400));
    hold.ended(play,wrap+1460);
    assert(!hold.holds(wrap+1460));
    hold.start(true,3*wrap-500);
    assert(hold.holds(3*wrap+1499) && !hold.holds(3*wrap+1500));
    assert(path(Sound::Notification)=="/tmp/ui/tc002/notification.mp3");
    assert(!canInterrupt(Sound::TimerExpired,Sound::Alarm) && canInterrupt(Sound::TimerExpired,Sound::Silence));
    assert(!canInterrupt(Sound::PomodoroRest,Sound::RestTick));
}
