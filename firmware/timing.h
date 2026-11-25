#pragma once
#include "input.h"
#include <algorithm>
#include <cstdio>
#include <string>
namespace tc {
using Millis = int64_t;
inline int clamp(int value, int low, int high) { return std::max(low,std::min(high,value)); }

class Elapsed {
    Millis accrued = 0;
    Millis start = 0;
public:
    bool running = false;
    Millis value(Millis now) const { return accrued + (running ? now-start : 0); }
    bool crossedSecond(Millis previous, Millis now) const {
        return running && value(now)/1000 > value(std::max(previous,start))/1000;
    }
    void toggle(Millis now) {
        accrued = value(now);
        start = now;
        running = !running;
    }
    void reset() { running = false; accrued = 0; }
};

inline std::string duration(Millis ms, bool tenths=false) {
    const int64_t seconds = std::max<Millis>(0,ms)/1000;
    char text[40];
    if (seconds >= 3600)
        snprintf(text,sizeof text,"%lld:%02d:%02d",static_cast<long long>(seconds/3600),
                 int(seconds/60%60),int(seconds%60));
    else if (tenths)
        snprintf(text,sizeof text,"%02d:%02d.%d",int(seconds/60),int(seconds%60),int(ms/100%10));
    else
        snprintf(text,sizeof text,"%02d:%02d",int(seconds/60),int(seconds%60));
    return text;
}

struct Timer {
    int minutes = 5;
    Elapsed elapsed;
    Millis left(Millis now) const { return minutes*60000LL - elapsed.value(now); }
    void command(Action a, Millis now) {
        if (a == Action::HoldCenter || (a == Action::Center && left(now) <= 0)) elapsed.reset();
        else if (a == Action::Center) elapsed.toggle(now);
        else if (!elapsed.running && elapsed.value(now) == 0) {
            if (a == Action::Plus || a == Action::Minus || a == Action::HoldPlus || a == Action::HoldMinus) {
                const int step = a == Action::HoldPlus ? 10 : a == Action::HoldMinus ? -10 : a == Action::Plus ? 1 : -1;
                minutes = clamp(minutes + step, 1, 1440);
            }
        }
    }
};
struct Interval {
    int focus, rest;
    Elapsed elapsed;
    Interval(int focusMinutes, int restMinutes) : focus(focusMinutes), rest(restMinutes) {}
    Millis phaseTime(Millis now) const { return elapsed.value(now) % ((focus+rest)*60000LL); }
    bool resting(Millis now) const { return phaseTime(now) >= focus*60000LL; }
    Millis remaining(Millis now) const {
        return (resting(now) ? focus+rest : focus)*60000LL - phaseTime(now);
    }
    void command(Action a, Millis now) {
        if (a == Action::Center) elapsed.toggle(now);
        if (a == Action::HoldCenter) elapsed.reset();
    }
};

constexpr int pomoMinFocus = 25, pomoMaxFocus = 45, pomoFocusStep = 5;
inline int pomoFocusMinutes(int minutes) {
    if (minutes < pomoMinFocus || minutes > pomoMaxFocus || (minutes-pomoMinFocus)%pomoFocusStep != 0)
        return pomoMinFocus;
    return minutes;
}

struct World {
    int base = 540;
    bool summer = false;
    int offset() const { return base + (summer ? 60 : 0); }
    void command(Action a) {
        if (a == Action::Center) summer = !summer;
        int step = 0;
        if (a == Action::Minus || a == Action::Plus) step = 15;
        if (a == Action::HoldMinus || a == Action::HoldPlus) step = 60;
        if (a == Action::Minus || a == Action::HoldMinus) step = -step;
        base = clamp(base + step,-720,840);
    }
    std::string label() const {
        const int n = std::abs(offset());
        char buf[16];
        if (n%60) snprintf(buf,sizeof buf,"%c%d:%02d",offset()<0?'-':'+',n/60,n%60);
        else snprintf(buf,sizeof buf,"%c%d",offset()<0?'-':'+',n/60);
        return buf;
    }
};
}
