#include "../../firmware/calendar.h"
#include <cassert>
int main() {
    auto jst=tc::localFields(1704034800);
    assert(jst.tm_year==124 && jst.tm_mon==0 && jst.tm_mday==1 && jst.tm_hour==0);
    auto west=tc::localFields(1704034800,-300);
    assert(west.tm_mday==31 && west.tm_hour==10);
    auto sun=tc::sunTimes(jst,35.68,139.77);
    assert(std::abs(sun.rise-411)<=4 && std::abs(sun.set-998)<=4);
    assert(tc::moonAge(947182440)==0 && tc::moonAge(947182440-86400)>28);
    assert(tc::hhmm(1023)=="17:03");
}
