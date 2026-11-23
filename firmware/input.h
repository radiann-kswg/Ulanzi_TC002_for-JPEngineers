#pragma once
#include <array>
#include <cstdint>

namespace tc {
enum class Key { Knob, Minus, Center, Plus };
enum class Action { None, Knob, HoldKnob, Minus, HoldMinus, Center, HoldCenter,
                    Plus, HoldPlus, Busy, Quieter, Louder, Previous, Next };

class Input {
    struct Button {
        bool down = false;
        bool consumed = false;
        int64_t since = 0;
    };
    std::array<Button, 4> buttons{};
public:
    Action rotate(bool clockwise) const {
        if (buttons[0].down) return Action::None;
        return clockwise ? Action::Next : Action::Previous;
    }
    Action edge(Key key, bool pressed, int64_t now) {
        const int i = static_cast<int>(key);
        Button& current = buttons[i];
        if (current.down == pressed) return Action::None;
        current.down = pressed;
        if (pressed) {
            current.since = now;
            current.consumed = false;
            if (buttons[0].down) {
                for (int side = 1; side <= 3; ++side) {
                    if (buttons[side].down && !buttons[side].consumed) {
                        buttons[0].consumed = buttons[side].consumed = true;
                        const Action chords[] = {Action::Quieter, Action::Busy, Action::Louder};
                        return chords[side-1];
                    }
                }
            }
            return Action::None;
        }
        if (current.consumed) return Action::None;
        const Action taps[] = {Action::Knob, Action::Minus, Action::Center, Action::Plus};
        const Action holds[] = {Action::HoldKnob, Action::HoldMinus, Action::HoldCenter, Action::HoldPlus};
        return now - current.since >= 650 ? holds[i] : taps[i];
    }
};

enum class Level { Category, Menu, Screen };
struct Navigation {
    Level level = Level::Screen;
    int category = 3;
    std::array<int,4> page{{0,0,0,1}};
    bool busy = false;
    bool navigate(Action a) {
        if (a == Action::Busy) { busy = !busy; return true; }
        if (busy) return false;
        if (a == Action::Knob) {
            level = level == Level::Menu ? Level::Category : Level::Menu;
            return true;
        }
        if (a == Action::HoldKnob && level == Level::Menu) { level = Level::Screen; return true; }
        if ((a == Action::Next || a == Action::Previous) && level != Level::Screen) {
            int& index = level == Level::Category ? category : page[category];
            const int count = level == Level::Category ? 4 : 8;
            index = (index + count + (a == Action::Next ? 1 : -1)) % count;
            return true;
        }
        return false;
    }
};
}
