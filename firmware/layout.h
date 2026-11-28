#pragma once
#include "display.h"
#include "feed.h"

namespace tc {
constexpr uint32_t ivory=0xD3E4DE, green=0x51D8A0, amber=0xF7B556, blue=0x73BDFA;
enum class Icon { None, Hourglass, Stopwatch, Tomato, Cup, Briefcase, Play, Pause };
struct Layout {
    std::string main, sub, stampLine, weatherKind;
    uint32_t color=ivory;
    int gauge=-1, weekday=-1, weekdayStyle=-1, weekdayMode=-1;
    bool compact=false;
    Icon icon=Icon::None;
    bool paused=false, ready=false, automatic=false;
    int calendarPanel=-1, moonTenths=0;
    bool calendarHoliday=false;
    int service=-1, servicePage=-1;
    bool menu=false, popup=false;
};

inline int weekdayStyle(int weekday,bool holiday,WeekdayColoring mode) {
    switch (mode) {
    case WeekdayColoring::Sunday: return weekday==6?6:-1;
    case WeekdayColoring::SundayHoliday: return holiday || weekday==6?6:-1;
    case WeekdayColoring::WeekendHoliday: return holiday || weekday==6?6:weekday==5?5:-1;
    case WeekdayColoring::AllWeekdays: return weekday;
    case WeekdayColoring::AllHolidays: return holiday?6:weekday;
    }
    return -1;
}
}
