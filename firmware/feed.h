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
struct Feed {
    int64_t generated = 0;
    bool hasLocation = false;
    double latitude = 0, longitude = 0;
    std::string place;
    std::array<std::array<std::vector<Row>,8>,4> pages;
    std::vector<Notice> events;
    std::vector<std::string> weatherKinds;
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
        int64_t c=0,p=0,stamp=0;
        if (f[0]=="at" && f.size()==2 && integer(f[1],stamp) && stamp>0) next.generated=stamp;
        else if (f[0]=="place" && f.size()==4 && coordinate(f[1],90,next.latitude)
                 && coordinate(f[2],180,next.longitude)) { next.place=f[3]; next.hasLocation=true; }
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
