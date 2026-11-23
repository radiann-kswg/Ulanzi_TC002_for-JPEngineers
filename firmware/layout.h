#pragma once
#include "display.h"

namespace tc {
constexpr uint32_t ivory=0xD3E4DE, green=0x51D8A0, amber=0xF7B556, blue=0x73BDFA;
enum class Icon { None, Hourglass, Stopwatch, Tomato, Cup };
struct Layout {
    std::string main, sub, stampLine, weatherKind;
    uint32_t color=ivory;
    int gauge=-1, weekday=-1;
    bool compact=false;
    Icon icon=Icon::None;
    bool paused=false, ready=false, automatic=false;
    int calendarPanel=-1, moonTenths=0;
    int service=-1, servicePage=-1;
    bool menu=false;
};
}
