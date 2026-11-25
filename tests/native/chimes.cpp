#include "../../firmware/clock.h"
#include <cassert>
using namespace tc;

// 2024-01-01 00:00:00 UTC. Convert the displayed boundary back to UTC for each dial.
constexpr time_t midnightUTC=1704067200;

void day(int page,int offset,bool summer) {
    Clock clock;
    clock.nav.page[3]=page;
    clock.world.base=offset;
    clock.world.summer=summer;
    const int displayedOffset=page==0 ? clock.world.offset() : 540;
    for (int h=0;h<24;++h) {
        time_t top=midnightUTC+h*3600-displayedOffset*60;
        Millis start=h*3600000LL;
        clock.advance(start,top-1);
        int strikes=0,noons=0,midnights=0;
        Millis previous=-1000;
        for (int ms=0;ms<11000;ms+=50) {
            Sound cue=clock.advance(start+1000+ms,top+ms/1000);
            if (cue==Sound::Hour) {
                assert(ms-previous>=850);
                previous=ms;
                ++strikes;
            }
            noons+=cue==Sound::Noon;
            midnights+=cue==Sound::Midnight;
        }
        assert(strikes==h%12 && noons==(h==12) && midnights==(h==0));
    }
}
int main() {
    day(1,0,false);
    day(0,345,false);
    day(0,-210,true);
    day(0,840,false);
    Clock clock;
    clock.nav.page[3]=0;
    clock.world.base=0;
    time_t top=midnightUTC+11*3600;
    assert(clock.advance(0,top-1)==Sound::None);
    clock.feed.events.push_back({top,"dot-new-test","test"});
    assert(clock.advance(2000,top+1)==Sound::Hour);
    assert(!clock.popupActive && clock.pending.size()==1);
    clock.world.summer=true;
    assert(clock.advance(2100,top+1,false)==Sound::None);
    assert(clock.advance(2200,top+1)==Sound::Notification);
    assert(clock.advance(3000,top+2)==Sound::Tick);
    clock.advance(3600000,top+3599);
    clock.volume=0;
    assert(clock.advance(3601000,top+3600)==Sound::None);
    clock.volume=4;
    assert(clock.advance(3602000,top+3601)==Sound::Tick);
    // A wall-clock correction crossing an hour does not start a belated chime.
    assert(clock.advance(3603000,top+7200)==Sound::None);
    Clock corrected;
    corrected.nav.page[3]=0;
    corrected.world.base=0;
    top=midnightUTC+2*3600;
    corrected.advance(0,top-1);
    assert(corrected.advance(1000,top)==Sound::Hour);
    assert(corrected.advance(1200,top-1)==Sound::None);
    assert(corrected.advance(1600,top)==Sound::None);
    assert(corrected.advance(1850,top)==Sound::Hour);
    assert(corrected.advance(2700,top+1)==Sound::Tick);
}
