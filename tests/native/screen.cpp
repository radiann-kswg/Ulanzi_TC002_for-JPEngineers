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
    auto ready=screen(clock,4000,utc);
    assert(ready.icon==Icon::Play && ready.main=="30:00" && ready.sub.empty());
    clock.command(Action::Center,4000);
    auto busy=screen(clock,5000,utc);
    assert(busy.icon==Icon::Briefcase && busy.main=="29:59" && busy.color==amber);
    auto rest=screen(clock,1804000,utc);
    assert(rest.icon==Icon::Cup && rest.main=="05:00" && rest.color==blue);
    clock.command(Action::Center,1805000);
    auto paused=screen(clock,1810000,utc);
    assert(paused.icon==Icon::Pause && paused.main=="04:59" && paused.color==blue);
    clock.command(Action::HoldCenter,1810010);
    clock.busy.focus=60;
    auto hour=screen(clock,1810020,utc);
    assert(hour.main=="1:00:00" && hour.icon==Icon::Play);
    Clock counters;
    counters.nav.page[3]=5;
    auto timer=screen(counters,0,utc);
    assert(timer.icon==Icon::Hourglass);
    Glyph digit{'?',6,5,{31},0};
    Font numbers{&digit,1};
    Font empty{&digit,0};
    Clock menus;
    for (Level level:{Level::Category,Level::Menu}) {
        menus.nav.level=level;
        for (int c=0;c<4;++c) for (int p=0;p<8;++p) {
            menus.nav.category=c; menus.nav.page[c]=p;
            auto menu=screen(menus,0,utc);
            auto pixels=paint(menu,numbers,numbers,numbers,0);
            int count=level==Level::Category?4:8, width=40/count;
            int selected=level==Level::Category?c:p;
            for (int x=0;x<40;++x) {
                int red=x%width==width-1?0:x/width==selected?(c==3?blue:serviceInk(c))>>16:0x24;
                assert(pixels.pixels[(15*52+12+x)*3]==red);
            }
            if (c==3) {
                Frame previous;
                line(previous,menu.main,numbers,numbers,2,blue);
                assert(std::equal(pixels.pixels.begin(),pixels.pixels.begin()+15*52*3,previous.pixels.begin()));
            }
        }
    }
    for (const auto& state:{ready,busy,rest,paused,hour}) {
        auto frame=paint(state,numbers,empty,empty,0);
        // All states use the large face on the right, including the hour preset.
        assert(frame.pixels[(4*52+51)*3] && frame.refreshAfter==std::numeric_limits<int>::max());
        const int firstDigit=52-TextRun(state.main,numbers,empty).width;
        assert(firstDigit>10 && frame.pixels[(4*52+firstDigit)*3]);
        assert(frame.pixels[(4*52+10)*3]==0);
    }
    auto face=paint(timer,numbers,numbers,numbers,0);
    assert(face.pixels[(2*52+1)*3] && face.pixels[(2*52+51)*3]);
    assert(face.pixels[(2*52+9)*3]==0);
    counters.nav.page[3]=6;
    counters.stopwatch.toggle(0);
    auto watch=screen(counters,3600000,utc);
    assert(watch.icon==Icon::Stopwatch && watch.main=="1:00:00");
    counters.nav.page[3]=4;
    auto pomoReady=screen(counters,0,utc);
    assert(pomoReady.ready && pomoReady.main=="25:00");
    counters.pomo.command(Action::Center,0);
    assert(screen(counters,1000,utc).icon==Icon::Tomato);
    assert(screen(counters,25*60000,utc).icon==Icon::Cup);
    counters.pomo.command(Action::Center,25*60000+100);
    assert(screen(counters,25*60000+200,utc).paused);

    Clock pop;
    std::string title="長い通知のスクロールを末尾のタイトルまで確認する";
    pop.feed.events={{100000,"schedule-1-test-100000",title},{100001,"ci","復旧 main"}};
    pop.advance(0,100000);
    assert(screen(pop,0,100000).service==1 && screen(pop,0,100000).servicePage==0);
    auto popupFrame=paint(screen(pop,0,100000),numbers,numbers,numbers,0);
    TextRun popupText("予定 "+title,numbers,numbers);
    assert(popupFrame.advanceAfter==popupText.readTime(developerWidth) && popupFrame.advanceAfter>3500);
    pop.advance(3500,100003);
    assert(screen(pop,3500,100003).service==1);
    pop.advance(90000,100090); // A delayed UI tick does not skip any unread pixels.
    auto tail=paint(screen(pop,90000,100090),numbers,numbers,numbers,popupFrame.advanceAfter-1);
    Frame expectedTail;
    popupText.draw(expectedTail,2,ivory,popupFrame.advanceAfter-1,developerLeft);
    for (int y=0;y<16;++y) for (int x=developerLeft;x<52;++x) {
        auto pos=(y*52+x)*3;
        assert(std::equal(tail.pixels.begin()+pos,tail.pixels.begin()+pos+3,expectedTail.pixels.begin()+pos));
    }
    pop.nextPopup();
    assert(screen(pop,3500,100003).servicePage==2 && screen(pop,3500,100003).service==0);
    pop.nextPopup();
    assert(screen(pop,7000,100007).weekday>=0);
    pop.command(Action::Louder,8000);
    assert(screen(pop,8000,100008).service==-1);
}
