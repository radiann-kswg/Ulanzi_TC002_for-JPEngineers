#include "../../firmware/clock.h"
#include <cassert>
using namespace tc;

void counterTicks(int page,bool busy) {
    Clock clock;
    clock.nav.page[3]=page;
    if (busy) clock.command(Action::Busy,0);
    auto advance=[&](Millis now) { return clock.advance(now,1704034800+now/1000); };
    assert(advance(1000)==Sound::None);
    clock.command(Action::Center,1250);
    assert(advance(2249)==Sound::None && advance(2250)==Sound::Tick);
    assert(advance(2300)==Sound::None && advance(3250)==Sound::Tick);
    clock.command(Action::Center,3350);
    assert(advance(5700)==Sound::None);
    clock.command(Action::Center,6000);
    assert(advance(6899)==Sound::None && advance(6900)==Sound::Tick);
    clock.command(Action::HoldCenter,6950);
    assert(advance(8000)==Sound::None);
}

int main() {
    counterTicks(4,false);
    counterTicks(5,false);
    counterTicks(6,false);
    counterTicks(1,true);

    Clock app;
    auto t=1704034800;
    app.advance(0,t-1);
    assert(app.advance(1000,t)==Sound::Midnight);
    assert(app.advance(1050,t)==Sound::None);
    assert(app.advance(2000,t+1)==Sound::Tick);
    assert(app.advance(60000,t+59)==Sound::None);
    assert(app.advance(61000,t+60)==Sound::Minute);
    app.advance(3599000,t+3599);
    assert(app.advance(3600000,t+3600)==Sound::Hour);
    app.nav.page[3]=5; app.timer.minutes=1;
    app.command(Action::Center,1000);
    app.command(Action::Busy,2000);
    app.feed.events.push_back({t+61,"x","CI"});
    assert(app.advance(62000,t+61)==Sound::Alarm && app.pending.empty());
    app.command(Action::Busy,63000);
    assert(app.command(Action::Center,63000)==Sound::Silence);
    assert(!app.timer.elapsed.running && app.timer.left(63001)==60000);
    assert(app.advance(64000,t+63)==Sound::None && app.noticeUntil==0);
    app.nav.page[3]=0;
    app.command(Action::Plus,65000); app.command(Action::HoldPlus,67000);
    assert(app.world.base==615);
    Clock offline;
    offline.nav.busy=true;
    offline.feed.generated=t-120;
    offline.feed.events={{t,"schedule-1-job-1","確認"},{t+300,"schedule-1-job-2","確認"}};
    offline.advance(1000,t);
    assert(offline.pending.empty() && offline.notice.empty());
    assert(offline.scheduleRows(1,0,t).size()==1);
    assert(offline.scheduleRows(1,1,t).at(0).text.find("00:05")!=std::string::npos);
    offline.advance(1100,t);
    assert(offline.scheduleRows(1,0,t).size()==1);

    Clock collision;
    collision.pomo.focus=1; collision.timer.minutes=1;
    collision.pomo.command(Action::Center,0); collision.timer.command(Action::Center,0);
    collision.advance(59000,t-1);
    assert(collision.advance(60000,t)==Sound::Alarm);
    assert(collision.advance(60100,t)==Sound::None);
    collision.nav.page[3]=5;
    assert(collision.command(Action::Center,60101)==Sound::Silence);
    assert(collision.advance(60200,t)==Sound::None);

    Clock parallel;
    parallel.nav.page[3]=6;
    parallel.timer.elapsed.toggle(0);
    parallel.stopwatch.toggle(250);
    parallel.command(Action::Busy,500);
    parallel.busy.focus=parallel.busy.rest=1;
    parallel.command(Action::Center,500);
    assert(parallel.advance(1000,t)==Sound::None);
    assert(parallel.advance(1250,t)==Sound::None);
    assert(parallel.advance(1500,t)==Sound::Tick);
    assert(parallel.advance(60500,t+59)==Sound::Rest);
    assert(parallel.advance(61500,t+60)==Sound::Tick);
    assert(parallel.advance(120500,t+119)==Sound::Resume);
    parallel.command(Action::Busy,120550);
    assert(parallel.advance(121000,t+120)==Sound::None);
    assert(parallel.advance(121250,t+120)==Sound::Tick);
    parallel.nav.page[3]=1;
    assert(parallel.advance(121500,t+120)==Sound::None);
    assert(parallel.advance(122000,t+121)==Sound::Tick);
    assert(parallel.advance(122250,t+121)==Sound::None);
    assert(parallel.advance(179500,t+179)==Sound::None);
    assert(parallel.advance(180000,t+180)==Sound::Minute);
    assert(parallel.advance(180500,t+180)==Sound::Rest);

    Clock pomodoro;
    pomodoro.nav.page[3]=4;
    for (int old : {10,15,28,60}) assert(pomoFocusMinutes(old)==25);
    assert(pomodoro.pomo.focus==25);
    for (int minutes : {30,35,40,45,25}) {
        pomodoro.command(Action::Minus,0);
        assert(pomodoro.pomo.focus==minutes);
        assert(pomodoro.notice=="活動 "+std::to_string(minutes)+"分");
    }
    pomodoro.command(Action::Center,250);
    pomodoro.command(Action::Minus,350);
    pomodoro.timer.elapsed.toggle(500);
    assert(pomodoro.advance(1250,t)==Sound::Tick);
    assert(pomodoro.advance(1500,t)==Sound::None);
    pomodoro.timer.elapsed.reset();
    pomodoro.command(Action::Knob,1600);
    assert(pomodoro.advance(2250,t+1)==Sound::Tick);
    assert(pomodoro.advance(25*60000+250,t+1500)==Sound::Rest);
    assert(pomodoro.advance(25*60000+1250,t+1501)==Sound::Tick);
    assert(pomodoro.advance(35*60000+250,t+2100)==Sound::Resume);
}
