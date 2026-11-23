#include "../../firmware/clock.h"
#include <cassert>
using namespace tc;
int main() {
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
}
