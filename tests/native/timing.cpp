#include "../../firmware/timing.h"
#include <cassert>
using namespace tc;
int main() {
    World world;
    world.base = 330;
    world.command(Action::Plus);
    world.command(Action::HoldPlus);
    assert(world.label() == "+6:45");
    world.command(Action::Center);
    assert(world.label() == "+7:45");
    world.base = -45; world.summer=false;
    assert(world.label() == "-0:45");
    Timer timer;
    timer.minutes=1;
    timer.command(Action::Center, 9000);
    assert(timer.left(74000) == -5000);
    timer.command(Action::Center,74000);
    assert(!timer.elapsed.running && timer.left(80000) == 60000);
    Interval busy(30,5), pomo(10,10);
    busy.command(Action::Center, 0);
    pomo.command(Action::Center, 0);
    assert(pomo.resting(600000) && !busy.resting(600000));
    pomo.command(Action::Center, 600000);
    assert(pomo.remaining(9999999) == 600000);
    assert(!busy.resting(2100000) && busy.remaining(2100000)==1800000);
    assert(duration(3599900,true) == "59:59.9" && duration(3600000,true)=="1:00:00");
}
