#pragma once
#include <array>
#include <cerrno>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <istream>
#include <string>
#include <vector>
namespace tc {
struct Row { int64_t stamp; std::string text; bool stale; };
struct Notice { int64_t due; std::string id, text; };
enum class WeekdayColoring { Sunday, SundayHoliday, WeekendHoliday, AllWeekdays, AllHolidays };
struct Holiday { int date, offset; std::string region, name; };
inline bool weekdayColoring(const std::string& value,WeekdayColoring& result) {
    static const char* names[]={"sunday","sunday_holiday","weekend_holiday","all_weekdays","all_holidays"};
    for (int i=0;i<5;++i) if (value==names[i]) {
        result=static_cast<WeekdayColoring>(i); return true;
    }
    return false;
}
struct Feed {
    int64_t generated = 0;
    bool hasLocation = false;
    double latitude = 0, longitude = 0;
    std::string place;
    std::array<std::array<std::vector<Row>,8>,4> pages;
    std::vector<Notice> events;
    std::vector<std::string> weatherKinds;
    std::vector<Holiday> holidays;
    WeekdayColoring weekday=WeekdayColoring::AllHolidays;
};
inline bool integer(const std::string& s,int64_t& value) {
    char* end=nullptr; errno=0;
    value=strtoll(s.c_str(),&end,10);
    return !s.empty() && errno==0 && end==s.c_str()+s.size();
}
inline bool coordinate(const std::string& s,double bound,double& value) {
    char* end=nullptr; value=strtod(s.c_str(),&end);
    return !s.empty() && end==s.c_str()+s.size() && std::isfinite(value) && std::abs(value)<=bound;
}
// The bridge replaces a complete bounded TSV file atomically over Wi-Fi ADB.
inline bool readFeed(std::istream& file,Feed& result) {
    Feed next;
    std::string line;
    if (!std::getline(file,line) || line!="TC002/1") return false;
    size_t bytes=0;
    while (std::getline(file,line)) {
        bytes+=line.size()+1;
        if (bytes>262144 || line.size()>2048) return false;
        std::vector<std::string> f;
        size_t start=0,tab;
        while ((tab=line.find('\t',start))!=std::string::npos) {
            f.push_back(line.substr(start,tab-start)); start=tab+1;
        }
        f.push_back(line.substr(start));
        int64_t c=0,p=0,stamp=0,offset=0;
        if (f[0]=="at" && f.size()==2 && integer(f[1],stamp) && stamp>0) next.generated=stamp;
        else if (f[0]=="place" && f.size()==4 && coordinate(f[1],90,next.latitude)
                 && coordinate(f[2],180,next.longitude)) { next.place=f[3]; next.hasLocation=true; }
        else if (f[0]=="weekday" && f.size()==2 && weekdayColoring(f[1],next.weekday)) {}
        else if (f[0]=="holiday" && f.size()==5 && f[1].size()==10 && f[1][4]=='-' && f[1][7]=='-' &&
                 integer(f[1].substr(0,4)+f[1].substr(5,2)+f[1].substr(8,2),stamp) &&
                 stamp>=20000101 && stamp<=21991231 && integer(f[2],offset) && offset>=-720 && offset<=840 &&
                 !f[3].empty() && f[3].size()<=12 && !f[4].empty() && f[4].size()<=512 &&
                 next.holidays.size()<2048)
            next.holidays.push_back({int(stamp),int(offset),f[3],f[4]});
        else if ((f[0]=="row" || f[0]=="old") && (f.size()==5 || f.size()==6) && integer(f[1],c) && c>=0 && c<4
                 && integer(f[2],p) && p>=0 && p<8 && integer(f[3],stamp) && stamp>=0) {
            if (next.pages[c][p].size()>=100) return false;
            if (f.size()==6 && (c!=3 || p!=3 || f[5].size()>12)) return false;
            if (c==3 && p==3) next.weatherKinds.push_back(f.size()==6?f[5]:"cloud");
            next.pages[c][p].push_back({stamp,f[4],f[0]=="old"});
        } else if (f[0]=="event" && f.size()==4 && integer(f[1],stamp)
                 && stamp>0 && !f[2].empty() && next.events.size()<128)
            next.events.push_back({stamp,f[2],f[3]});
        else if (line=="END" && next.generated && file.peek()==std::char_traits<char>::eof()) {
            if (!next.hasLocation && result.hasLocation) {
                next.hasLocation=true;
                next.place=result.place;
                next.latitude=result.latitude;
                next.longitude=result.longitude;
            }
            result=std::move(next); return true;
        } else return false;
    }
    return false;
}
}
