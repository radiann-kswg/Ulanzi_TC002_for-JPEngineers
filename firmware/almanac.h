#pragma once
#include "calendar.h"
#include "display.h"

namespace tc {
// Nine-pixel symbols reserve the rest of the panel for the actual observation.
inline void weatherMark(Frame& frame,const std::string& kind,uint32_t color) {
    struct Mark { const char* kind; uint16_t rows[12]; };
    static const Mark marks[]={
        {"place",{56,68,130,146,130,68,40,16}},
        {"sun",{16,130,56,68,325,68,56,130,16}},
        {"partly",{4,42,20,42,120,132,258,511}},
        {"cloud",{0,0,56,68,130,258,511}},
        {"fog",{0,56,68,130,255,0,124,0,254}},
        {"rain",{56,68,130,255,0,68,34,0,17}},
        {"storm",{56,68,130,255,16,8,60,16,8}},
        {"snow",{16,146,84,56,511,56,84,146,16}},
        {"temp",{12,18,18,26,26,45,45,30}},
        {"high",{12,82,242,90,26,45,45,30}},
        {"low",{12,82,82,250,90,45,45,30}},
        {"humidity",{16,16,40,68,130,146,130,68,56}},
        {"pressure",{56,68,130,146,138,130,124}},
        {"air",{0,96,128,254,0,126,128,96}}
    };
    for (const auto& mark:marks) if (kind==mark.kind) {
        frame.mask(mark.rows,9,0,3,color);
        return;
    }
}

inline void moonDisk(Frame& frame,double age) {
    const double angle=2*3.141592653589793*age/29.530588853;
    const double side=sin(angle),front=-cos(angle);
    for (int y=-3;y<=3;++y) for (int x=-3;x<=3;++x) {
        double z2=12.25-x*x-y*y;
        if (z2<0) continue;
        bool lit=x*side+sqrt(z2)*front>0;
        frame.pixel(42+x,3+y,lit?0xF5D18B:0x343048);
    }
}

inline void horizon(Frame& frame,bool rise) {
    // Arrow above the horizon points up at sunrise and down at sunset.
    static const uint16_t up[12]={16,56,84,16,0,56,68,511};
    static const uint16_t down[12]={16,16,84,56,16,56,68,511};
    frame.mask(rise?up:down,9,1,0,rise?0xF7B556:0xE18D77);
}
}
