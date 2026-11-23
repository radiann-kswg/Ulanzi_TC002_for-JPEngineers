#include "../../firmware/screen.h"
#include <cassert>
using namespace tc;
int main() {
    const time_t utc=1704034800;
    Clock clock;
    clock.nav.page[3]=2;
    clock.feed.hasLocation=true;
    clock.feed.latitude=34.754974; clock.feed.longitude=134.390354;
    auto date=screen(clock,0,utc);
    assert(date.calendarPanel==0 && date.main=="1/1");
    assert(clock.autoBrowse(4500));
    auto sunrise=screen(clock,4500,utc);
    assert(sunrise.calendarPanel==1 && sunrise.main!="--:--" && sunrise.sub==date.sub);
    assert(clock.autoBrowse(9000));
    auto sunset=screen(clock,9000,utc);
    assert(sunset.calendarPanel==2 && sunset.main>sunrise.main);
    assert(clock.autoBrowse(13500) && clock.selection==0);
    Frame waxing,waning;
    moonDisk(waxing,7.38); moonDisk(waning,22.15);
    assert(waxing.pixels[(3*52+44)*3]>waxing.pixels[(3*52+40)*3]);
    assert(waning.pixels[(3*52+44)*3]<waning.pixels[(3*52+40)*3]);

    clock.feed.generated=utc;
    clock.nav.page[3]=3;
    clock.feed.pages[3][3]={{utc,"長い地名をゆっくり表示",false},{utc,"晴れ",false}};
    clock.feed.weatherKinds={"place","sun"};
    auto first=screen(clock,14000,utc);
    assert(first.weatherKind=="place");
    Glyph fallback{'?',8,7,{127},0};
    Font font{&fallback,1};
    assert(paint(first,font,font,font,0).advanceAfter>3600);
    assert(clock.autoBrowse(20000) && screen(clock,20000,utc).weatherKind=="sun");
    clock.command(Action::Minus,20100);
    assert(clock.selection==0 && !screen(clock,20100,utc).automatic && clock.entered==20100);
    clock.command(Action::Busy,20200);
    assert(!clock.autoBrowse(30000) && clock.selection==0);
}
