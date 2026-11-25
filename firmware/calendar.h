#pragma once
#include <cmath>
#include <ctime>
#include <cstdio>
#include <cstdint>
#include <limits>
#include <string>

namespace tc {
inline bool usableEpoch(int64_t seconds) {
    return seconds >= 1577836800 && seconds <= std::numeric_limits<time_t>::max();
}
inline std::tm localFields(time_t epoch, int offsetMinutes=540) {
    time_t shifted = epoch + offsetMinutes * 60;
    std::tm result{};
    gmtime_r(&shifted,&result);
    return result;
}
inline std::string clockText(const std::tm& t, bool seconds=false) {
    char out[12];
    if (seconds) snprintf(out,sizeof out,"%02d:%02d:%02d",t.tm_hour,t.tm_min,t.tm_sec);
    else snprintf(out,sizeof out,"%02d:%02d",t.tm_hour,t.tm_min);
    return out;
}
struct SunTimes { int rise, set; };
// NOAA fractional-year approximation, 90.833 degree apparent zenith, local JST.
inline SunTimes sunTimes(const std::tm& date,double latitude,double longitude) {
    const double rad = 3.141592653589793 / 180;
    int y = date.tm_year + 1900;
    bool leap = y%4==0 && (y%100!=0 || y%400==0);
    double g = 360*rad * date.tm_yday / (leap ? 366 : 365);
    double eq = 229.18*(0.000075+0.001868*cos(g)-0.032077*sin(g)-0.014615*cos(2*g)-0.040849*sin(2*g));
    double dec = 0.006918-0.399912*cos(g)+0.070257*sin(g)-0.006758*cos(2*g)
                 +0.000907*sin(2*g)-0.002697*cos(3*g)+0.00148*sin(3*g);
    double h = (cos(90.833*rad)-sin(latitude*rad)*sin(dec))/(cos(latitude*rad)*cos(dec));
    if (!(h>=-1 && h<=1)) return {-1,-1};
    double noon = 720 - 4*longitude - eq + 540;
    double halfDay = 4*acos(h)/rad;
    return {int(lround(noon-halfDay)),int(lround(noon+halfDay))};
}
inline double moonAge(time_t epoch) {
    // Mean synodic month since the new moon of 2000-01-06 18:14 UTC.
    const double month = 29.530588853;
    double days = (double(epoch)-947182440.0)/86400.0;
    return days-month*floor(days/month);
}
inline std::string hhmm(int minutes) {
    if (minutes < 0) return "--:--";
    minutes %= 1440;
    char out[8]; snprintf(out,sizeof out,"%02d:%02d",minutes/60,minutes%60);
    return out;
}
}
