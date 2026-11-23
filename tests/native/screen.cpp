#include "../../firmware/screen.h"
#include <cassert>
using namespace tc;
int main() {
    Clock clock;
    time_t utc=1704034800;
    assert(screen(clock,0,utc).main=="00:00:00");
    for (int d=0;d<7;++d) {
        auto view=screen(clock,0,utc+d*86400);
        assert(view.weekday==d);
        Glyph chars[]={{'?',4,1,{0},0},{U'月',10,9,{256},0}};
        Font font{chars,2};
        auto f=paint(view,font,font,font,0);
        assert(f.pixels[(2*52+51)*3]==(d==0?0x51:0));
        for (int n=0;n<7;++n)
            for (int y=14;y<16;++y)
                assert(f.pixels[(y*52+2+7*n)*3]==(n==d?0x51:0x17));
    }
    clock.nav.page[3]=0;
    assert(screen(clock,0,utc+12).main=="00:00:12" && screen(clock,0,utc).sub=="+9 STD");
    clock.command(Action::Center,100);
    assert(screen(clock,100,utc).sub=="+10 DST");
    clock.world.base=765;
    assert(screen(clock,100,utc).sub=="+13:45 DST");
    clock.feed.generated=utc;
    for (int c=0;c<4;++c) {
        clock.nav.category=c;
        for (int p=0;p<8;++p) {
            clock.nav.page[c]=p;
            assert(!screen(clock,200,utc).main.empty());
        }
    }
    clock.nav.category=1; clock.nav.page[1]=2;
    clock.feed.pages[1][2].push_back({utc,"作業中",true});
    assert(screen(clock,0,utc).main=="作業中");
    assert(screen(clock,3900,utc).sub=="00:00");
    clock.command(Action::Busy,4000);
    assert(screen(clock,4000,utc).main=="BUSY READY");
    Clock counters;
    counters.nav.page[3]=5;
    auto timer=screen(counters,0,utc);
    assert(timer.icon==Icon::Hourglass);
    Glyph digit{'?',6,5,{31},0};
    Font numbers{&digit,1};
    auto face=paint(timer,numbers,numbers,numbers,0);
    assert(face.pixels[(2*52+1)*3] && face.pixels[(2*52+51)*3]);
    assert(face.pixels[(2*52+9)*3]==0);
    counters.nav.page[3]=6;
    counters.stopwatch.toggle(0);
    auto watch=screen(counters,3600000,utc);
    assert(watch.icon==Icon::Stopwatch && watch.main=="1:00:00");
    counters.nav.page[3]=4;
    assert(screen(counters,0,utc).ready);
    counters.pomo.command(Action::Center,0);
    assert(screen(counters,1000,utc).icon==Icon::Tomato);
    assert(screen(counters,600000,utc).icon==Icon::Cup);
    counters.pomo.command(Action::Center,600100);
    assert(screen(counters,600200,utc).paused);

    Clock pop;
    pop.feed.events={{100000,"schedule-1-test-100000","PR 今日の作業"},{100001,"ci","復旧 main"}};
    pop.advance(0,100000);
    assert(screen(pop,0,100000).service==1 && screen(pop,0,100000).servicePage==0);
    pop.advance(3500,100003);
    assert(screen(pop,3500,100003).servicePage==2 && screen(pop,3500,100003).service==0);
    assert(screen(pop,7000,100007).weekday>=0);
    pop.command(Action::Louder,8000);
    assert(screen(pop,8000,100008).service==-1);
}
