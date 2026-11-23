#pragma once
#include "layout.h"
#include <cstdlib>

namespace tc {
constexpr int developerLeft=12, developerWidth=52-developerLeft;
enum class Symbol { GitHub, Claude, Codex, Pull, Issue, Workflow, Review, Bell, Schedule, Working, Waiting, Sessions, Check, Cross, Quota, Cost, Power, Network };
inline void symbol(Frame& f,Symbol s,uint32_t ink) {
    static const uint16_t shapes[][12]={
    {12,18,210,300,196,68,52,12,12}, // GitHub
    {16,146,84,56,511,56,84,146,16}, // Claude
    {28,2,9,17,33,17,9,482,28}, // Codex
    {198,297,198,68,36,20,14,9,6}, // Pull
    {56,68,130,257,273,257,130,68,56}, // Issue
    {7,5,7,226,190,224,64,224,224}, // Workflow
    {124,130,369,297,146,124,8,4,0}, // Review
    {16,56,68,68,68,130,511,0,56}, // Bell
    {68,254,387,381,257,297,257,257,254}, // Schedule
    {4,12,28,60,124,60,28,12,4}, // Working
    {254,257,257,341,257,254,40,24,8}, // Waiting
    {240,144,190,226,34,62,0,0,0}, // Sessions
    {0,128,192,96,50,30,12,0,0}, // Check
    {0,130,68,40,16,40,68,130,0}, // Cross
    {56,68,146,281,305,146,68,56,0}, // Quota
    {56,68,84,68,56,0,124,130,124}, // Cost
    {0,127,65,221,221,221,65,127,0}, // Power
    {56,40,56,16,254,130,455,325,455}, // Network
    };
    f.mask(shapes[static_cast<unsigned>(s)],9,1,1,ink);
}
inline uint32_t serviceInk(int service) {
    static const uint32_t colors[]={0xC6A9FA,0xF0A581,0x77DCCA};
    return colors[service];
}
inline void signature(Frame& f,int service) {
    // A fork, a star, and a prompt remain identifiable below the status icon.
    static const uint16_t marks[][12]={{34,34,30,2},{20,127,28,34},{2,4,2,120}};
    f.mask(marks[service],7,2,12,serviceInk(service));
}
inline Symbol pageSymbol(int service,int page) {
    const Symbol brands[]={Symbol::GitHub,Symbol::Claude,Symbol::Codex};
    static const Symbol github[]={Symbol::Pull,Symbol::Pull,Symbol::Workflow,Symbol::Issue,
                                  Symbol::Issue,Symbol::Review,Symbol::Quota,Symbol::Power};
    static const Symbol ai[]={Symbol::Bell,Symbol::Schedule,Symbol::Working,Symbol::Waiting,
                              Symbol::Sessions,Symbol::Check,Symbol::Quota,Symbol::Power};
    return page<0?brands[service]:(service==0?github:ai)[page];
}
inline bool digitsOnly(const std::string& text) {
    return !text.empty() && text.find_first_not_of("0123456789")==std::string::npos;
}
inline std::string ticketTitle(const std::string& text) {
    // The bridge emits "[status ]repo#number title". Keep the title near the front.
    static const std::string prefixes[]={"草稿 ","PR 新規 ","PR 更新 ","PR 終了 ",
        "Issue 新規 ","Issue 更新 ","Issue 終了 ","依頼 ","自分 承認済 ","自分 審査待ち ",
        "自分 未審査 ","自分 変更依頼 "};
    size_t start=0;
    for (const auto& prefix:prefixes)
        if (text.compare(0,prefix.size(),prefix)==0) { start=prefix.size(); break; }
    size_t space=text.find(' ',start),hash=text.find('#',start);
    if (space==std::string::npos || hash==std::string::npos || hash<=start || hash>=space ||
        space+1>=text.size() || !digitsOnly(text.substr(hash+1,space-hash-1))) return text;
    std::string repo=text.substr(start,hash-start);
    if (repo.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")!=std::string::npos) return text;
    return text.substr(0,start)+text.substr(hash)+" / "+repo;
}
struct DevReading {
    Symbol mark;
    uint32_t ink;
    std::string text, upper, lower;
    bool numbers=false, pairedCounts=false, partial=false;
    int remainingBar=-1;
    std::string date, time;
    DevReading(const Layout& v):mark(pageSymbol(v.service,v.servicePage)),
        ink(serviceInk(v.service)),text(v.main) {
        if (v.menu) return;
        const int p=v.servicePage;
        if (p==7) {
            mark=v.gauge<0?Symbol::Network:Symbol::Power;
            numbers=v.gauge>=0;
        } else if (p==6) {
            const std::string extra="追加 ", remaining="残 ";
            if (text.compare(0,extra.size(),extra)==0) { mark=Symbol::Cost; text.erase(0,extra.size()); }
            else if (text.compare(0,remaining.size(),remaining)==0) text.erase(0,remaining.size());
            numbers=true;
            size_t split=text.find(" / ");
            if (mark==Symbol::Quota && split!=std::string::npos) {
                upper=text.substr(0,split); lower=text.substr(split+3);
            } else if (mark==Symbol::Quota && text.size()>1 && text.back()=='%') {
                char* end=nullptr;
                double pct=std::strtod(text.c_str(),&end);
                if (end==text.c_str()+text.size()-1 && pct>=0 && pct<=100)
                    remainingBar=int(pct*developerWidth/100+0.5);
            }
        } else if (v.service==0) {
            numbers=p==1 || p==4;
            if (p==0 || p==3 || p==5) text=ticketTitle(text);
            if (p==2) {
                size_t split=text.find(' ');
                std::string state=text.substr(0,split);
                static const struct { const char* key; const char* label; } names[]={
                    {"success","成功"},{"failure","失敗"},{"timed_out","時間切れ"},{"startup_failure","起動失敗"},
                    {"cancelled","中止"},{"skipped","スキップ"},{"action_required","要操作"},
                    {"in_progress","実行中"},{"queued","待機中"},{"completed","終了"}
                };
                for (const auto& name:names)
                    if (state==name.key) { text.replace(0,state.size(),name.label); break; }
                if (state=="failure" || state=="timed_out" || state=="startup_failure" || state=="失敗") {
                    mark=Symbol::Cross; ink=0xFA927C;
                } else if (state=="success" || state=="復旧") { mark=Symbol::Check; ink=green; }
            } else if (p==5) {
                if (text.compare(0,sizeof("自分 承認済 ")-1,"自分 承認済 ")==0) { mark=Symbol::Check; ink=green; }
                else if (text.compare(0,sizeof("依頼 ")-1,"依頼 ")==0) { mark=Symbol::Review; ink=amber; }
            }
        } else if (p==4) {
            const std::string prefix="確認分 ", active="作業 ", wait=" 待ち ";
            size_t start=text.compare(0,prefix.size(),prefix)==0?prefix.size():0;
            size_t sep=text.find(wait,start);
            if (text.compare(start,active.size(),active)==0 && sep!=std::string::npos) {
                auto work=text.substr(start+active.size(),sep-start-active.size());
                auto waiting=text.substr(sep+wait.size());
                if (digitsOnly(work) && digitsOnly(waiting)) {
                    upper=work; lower=waiting; pairedCounts=true; partial=start>0;
                }
            }
        } else if (p==3) ink=amber;
        else if (p==5) ink=green;
        else if (p<2 && text.size()>12 && text[2]=='/' && text[5]==' ' &&
                 text[8]==':' && text[11]==' ' && digitsOnly(text.substr(0,2)) &&
                 digitsOnly(text.substr(3,2)) && digitsOnly(text.substr(6,2)) && digitsOnly(text.substr(9,2))) {
            date=text.substr(0,5); time=text.substr(6,5); text.erase(0,12);
        }
        if (!v.stampLine.empty() || text=="取得不可" || text=="未取得" || text=="未接続" ||
            text=="電池 ?" || text=="Cowork 未取得" || text=="Code 未取得" || text=="次は未取得")
            ink=amber;
        else if (text=="該当なし" || text=="予定なし" || text=="通知なし" || text=="実行なし")
            ink=0x91A69F;
    }
};
inline void developerPanel(Frame& frame,const Layout& v,const Font& denki,const Font& nega,
                           const Font& maru,int64_t elapsed) {
    const int left=developerLeft, area=developerWidth;
    DevReading row(v);
    if (row.partial) {
        // The observed subset count is exact. 内 marks the limited coverage.
        line(frame,"内",denki,maru,0,amber);
    } else symbol(frame,row.mark,row.ink);
    signature(frame,v.service);
    TextRun value(row.text,denki,maru);
    if (v.menu) {
        value.draw(frame,1,ivory,elapsed,left);
        int count=v.servicePage<0?4:8;
        int choice=v.servicePage<0?v.service:v.servicePage;
        for (int i=0;i<count;++i) {
            int start=left+i*area/count;
            for (int x=start;x<left+(i+1)*area/count-1;++x)
                frame.pixel(x,15,i==choice?row.ink:0x243138);
        }
        return;
    }
    bool small=false;
    bool ascii=std::all_of(row.text.begin(),row.text.end(),[](unsigned char ch){ return ch<128; });
    if (row.numbers && value.width>area && ascii) {
        TextRun compact(row.text,nega,denki);
        if (compact.width<=area) { value=std::move(compact); small=true; }
    }
    TextRun upper(row.upper,nega,denki),lower(row.lower,nega,denki);
    int pairLeft=row.pairedCounts?20:left;
    bool pair=!row.upper.empty() && !row.lower.empty() &&
              std::max(upper.width,lower.width)<=52-pairLeft;
    int intro=row.date.empty()?0:2400;
    bool dated=!v.stampLine.empty();
    bool cycle=intro || dated;
    int read=pair?3600:std::max(3600,value.readTime(area));
    int period=intro+read+(dated?3000:0);
    int64_t phase=cycle?elapsed%period:elapsed;
    if (phase<intro) {
        TextRun(row.date,nega,denki).draw(frame,0,row.ink,0,left,true);
        TextRun(row.time,nega,denki).draw(frame,8,ivory,0,left,true);
        frame.wake(int(intro-phase));
        return;
    }
    phase-=intro;
    if (dated && phase>=read) {
        // A 3x5 OFF/OLD tag leaves room for the full date without scrolling.
        static const uint16_t off[12]={1906,277,821,277,274},old[12]={786,1301,1301,1301,882};
        frame.mask(v.stampLine.compare(0,3,"OFF")==0?off:old,11,left,1,amber);
        TextRun(v.stampLine.substr(4),nega,denki).draw(frame,0,ivory,0,left+12,true);
        TextRun(v.sub,nega,denki).draw(frame,8,ivory,0,left,true);
        frame.wake(int(read+3000-phase));
        return;
    }
    if (pair) {
        upper.draw(frame,0,dated?amber:ivory,0,pairLeft,true);
        lower.draw(frame,8,(dated || row.pairedCounts)?amber:ivory,0,pairLeft,true);
        if (row.pairedCounts) {
            static const uint16_t play[12]={1,3,7,3,1}, bubble[12]={31,17,31,2};
            frame.mask(play,3,13,2,green); frame.mask(bubble,5,12,10,amber);
        }
    } else {
        int end=value.readTime(area);
        value.draw(frame,small?4:2,dated?amber:ivory,cycle?std::min<int64_t>(phase,end-1):phase,left,row.numbers);
        if (cycle && phase>=end) frame.refreshAfter=std::numeric_limits<int>::max();
    }
    if (cycle) frame.wake(int(read-phase));
    int fill=v.gauge>=0 && v.main!="電池 ?"?v.gauge*area/52:row.remainingBar;
    if (fill>=0) for (int i=0;i<area;++i)
        frame.pixel(left+i,15,i<fill?row.ink:0x243138);
}
}
