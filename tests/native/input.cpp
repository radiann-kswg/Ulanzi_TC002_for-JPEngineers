#include "../../firmware/input.h"
#include <cassert>
using namespace tc;
int main() {
    for (bool knobFirst : {true, false}) for (bool releaseKnobFirst : {true, false}) {
        Input keys;
        Key first = knobFirst ? Key::Knob : Key::Plus;
        Key second = knobFirst ? Key::Plus : Key::Knob;
        assert(keys.edge(first, true, 0) == Action::None);
        assert(keys.edge(second, true, 500) == Action::Louder);
        assert(keys.edge(releaseKnobFirst ? Key::Knob : Key::Plus, false, 900) == Action::None);
        assert(keys.edge(releaseKnobFirst ? Key::Plus : Key::Knob, false, 950) == Action::None);
    }
    Input keys;
    keys.edge(Key::Knob,true,0);
    for (int i=0; i<2; ++i) {
        assert(keys.edge(Key::Center,true,20+i*50) == Action::Busy);
        assert(keys.edge(Key::Center,false,30+i*50) == Action::None);
    }
    assert(keys.edge(Key::Knob,false,1000) == Action::None);
    keys.edge(Key::Plus,true,1000);
    assert(keys.edge(Key::Plus,false,1650) == Action::HoldPlus);
    Navigation nav;
    nav.navigate(Action::Knob);
    nav.navigate(Action::Previous);
    nav.navigate(Action::HoldKnob);
    assert(nav.category == 3 && nav.page[3] == 0 && nav.level == Level::Screen);
    nav.navigate(Action::Busy);
    assert(!nav.navigate(Action::Next));
    nav.navigate(Action::Busy);
    assert(!nav.busy && nav.page[3] == 0);
}
