#pragma once
#include "clock.h"
#include "almanac.h"
#include "developer.h"

namespace tc {
inline std::string quotaWindow(const std::string& window,time_t utc) {
    const std::string marker=" リセット ";
    size_t pos=window.find(marker);
    if (pos==std::string::npos) return window;
    auto value=window.substr(0,pos);
    size_t space=value.find_last_of(' ');
    if (space!=std::string::npos) value.erase(0,space+1);
    std::tm reset{};
    const char* end=strptime(window.c_str()+pos+marker.size(),"%Y-%m-%dT%H:%M:%SZ",&reset);
    if (!end || *end) return "-- "+value;
    time_t deadline=timegm(&reset);
    if (deadline<0) return "-- "+value;
    int64_t seconds=int64_t(deadline)-utc;
    if (seconds<=0) return "0m --%";
    if (seconds>=86400) return std::to_string(seconds/86400)+"d "+value;
    if (seconds>=3600) return std::to_string(seconds/3600)+"h "+value;
    if (seconds<60) return "<1m "+value;
    return std::to_string(seconds/60)+"m "+value;
}
inline std::string quotaCountdown(const std::string& text,time_t utc) {
    const std::string prefix="残 ";
    if (text.compare(0,prefix.size(),prefix)!=0 || text.find(" リセット ")==std::string::npos) return text;
    auto windows=text.substr(prefix.size());
    size_t split=windows.find(" / ");
    auto result=prefix+quotaWindow(windows.substr(0,split),utc);
    if (split!=std::string::npos) result+=" / "+quotaWindow(windows.substr(split+3),utc);
    return result;
}
inline Layout screen(const Clock& clock, Millis now, time_t utc) {
    Layout v;
    const auto& nav=clock.nav;
    int c=nav.category,p=nav.page[c];
    auto local=localFields(utc);
    if (clock.alarmActive && !(c==3 && p==5 && !nav.busy && nav.level==Level::Screen)) {
        // Alternate the alarm with the current view so navigation remains usable.
        if ((now/1500)%2==0) { v.main="時間です"; v.color=amber; return v; }
    }
    if (clock.popupActive || clock.noticeUntil>now) {
        v.main=clock.notice; v.color=amber;
        v.popup=clock.popupActive;
        v.service=clock.noticeService; v.servicePage=clock.noticePage;
        return v;
    }
    if (!nav.busy && nav.level!=Level::Screen) {
        v.main=nav.level==Level::Category?categoryName(c):pageName(c,p);
        v.menu=true;
        v.servicePage=nav.level==Level::Category?-1:p;
        if (c<3) v.service=c;
        v.color=blue; return v;
    }
    if (nav.busy || (c==3 && p==4)) {
        const Interval& t=nav.busy?clock.busy:clock.pomo;
        bool rest=t.resting(now);
        if (!nav.busy) {
            v.icon=rest?Icon::Cup:Icon::Tomato;
            v.main=duration(t.remaining(now)+999);
            v.ready=!t.elapsed.running && !t.elapsed.value(now);
            v.paused=!t.elapsed.running && !v.ready;
            v.color=rest?blue:amber;
            return v;
        }
        v.compact=true; v.main=t.elapsed.running?(rest?"REST":"BUSY"):
            t.elapsed.value(now)?"PAUSE":"BUSY READY";
        v.sub=duration(t.remaining(now)+999); v.color=rest?blue:amber;
        return v;
    }
    if (c<3) { v.service=c; v.servicePage=p; }
    if (p==7) {
        if (clock.selection%2==0) {
            v.main=clock.battery<0?"電池 ?":std::to_string(clock.battery)+"%";
            v.gauge=clock.battery<0?0:clock.battery*52/100;
        } else { v.main=clock.ip.empty()?"未接続":clock.ip; }
        return v;
    }
    if (c==3 && p==0) {
        v.main=clockText(localFields(utc,clock.world.offset()),true);
        v.sub=clock.world.label()+(clock.world.summer?" DST":" STD");
        v.compact=true;
        return v;
    }
    if (c==3 && p==1) {
        v.main=clockText(local,true);
        v.weekday=(local.tm_wday+6)%7; // Monday first, like the stock weekStart=1 setting.
        return v;
    }
    if (c==3 && p==2) {
        v.calendarPanel=int(clock.selection%3);
        v.moonTenths=int(lround(moonAge(utc)*10));
        char buf[32];
        if (!v.calendarPanel) {
            snprintf(buf,sizeof buf,"%d/%d",local.tm_mon+1,local.tm_mday); v.main=buf;
        } else {
            SunTimes sun=clock.feed.hasLocation?sunTimes(local,clock.feed.latitude,clock.feed.longitude):SunTimes{-1,-1};
            v.main=hhmm(v.calendarPanel==1?sun.rise:sun.set);
        }
        snprintf(buf,sizeof buf,"%d.%d",v.moonTenths/10,v.moonTenths%10);
        v.sub=buf;
        return v;
    }
    if (c==3 && p==5) {
        v.icon=Icon::Hourglass;
        auto left=clock.timer.left(now);
        v.main=left>0?duration(left+999):"+"+duration(-left);
        v.gauge=int(std::max<Millis>(0,left)*52/(clock.timer.minutes*60000LL));
        v.color=left<=0?amber:green; return v;
    }
    if (c==3 && p==6) {
        v.icon=Icon::Stopwatch;
        v.main=duration(clock.stopwatch.value(now),true); return v;
    }
    std::vector<Row> scheduled;
    bool isSchedule=(c==1 || c==2) && p<2;
    if (isSchedule) scheduled=clock.scheduleRows(c,p,utc);
    const auto& rows=isSchedule?scheduled:clock.feed.pages[c][p];
    if (rows.empty()) {
        v.main=c<3 && p==6?(clock.selection%2?"追加 取得不可":"残 取得不可"):"未取得";
        return v;
    }
    const Row& row=rows[clock.selection%rows.size()];
    if (c==3 && p==3) {
        size_t index=clock.selection%rows.size();
        v.weatherKind=index<clock.feed.weatherKinds.size()?clock.feed.weatherKinds[index]:"cloud";
        v.automatic=clock.autoAt>=0 && clock.entered==clock.autoAt;
    }
    const bool disconnected=utc-clock.feed.generated>90 || clock.feed.generated>utc+90;
    const bool stale=row.stale || disconnected;
    v.main=c<3 && p==6?quotaCountdown(row.text,utc):row.text;
    if (stale) {
        if (!row.stamp) {
            if (c>=3 || p!=6) v.main="未取得";
        }
        else {
            auto t=localFields(row.stamp);
            char date[32]; snprintf(date,sizeof date,"%02d/%02d",t.tm_mon+1,t.tm_mday);
            // Keep both rows in the eight-pixel ASCII face.
            v.stampLine=std::string(disconnected?"OFF ":"OLD ")+date; v.sub=clockText(t);
        }
        v.color=amber;
    }
    return v;
}

inline Frame paint(const Layout& view,const Font& denki,const Font& nega,const Font& maru,Millis elapsed) {
    Frame frame;
    if (view.service>=0) {
        developerPanel(frame,view,denki,nega,maru,elapsed);
        return frame;
    }
    if (view.popup) {
        TextRun value(view.main,denki,maru);
        int end=value.readTime(52);
        frame.advanceAfter=std::max(3500,end);
        value.draw(frame,2,view.color,std::min<Millis>(elapsed,end-1));
        if (elapsed>=end-1) frame.refreshAfter=std::numeric_limits<int>::max();
        return frame;
    }
    if (view.menu) {
        line(frame,view.main,denki,maru,2,view.color,elapsed);
        menuBar(frame,view.servicePage<0?3:view.servicePage,view.servicePage<0?4:8,view.color);
        return frame;
    }
    if (view.calendarPanel>=0) {
        moonDisk(frame,view.moonTenths/10.);
        TextRun(view.sub,nega,denki).draw(frame,8,ivory,0,33,true);
        if (view.calendarPanel) {
            horizon(frame,view.calendarPanel==1);
            line(frame,view.main,nega,denki,8,ivory);
        } else line(frame,view.main,denki,maru,2,ivory);
        frame.advanceAfter=4500;
    } else if (view.icon!=Icon::None) {
        static const uint16_t hourglass[12]={127,34,34,20,8,20,34,42,54,127};
        static const uint16_t stopwatch[12]={28,8,92,34,73,73,81,65,34,28};
        static const uint16_t tomato[12]={8,42,28,62,127,123,127,62};
        static const uint16_t cup[12]={10,20,0,63,97,97,63,30};
        bool pomo=view.icon==Icon::Tomato || view.icon==Icon::Cup;
        const uint16_t* mark=view.icon==Icon::Hourglass?hourglass:view.icon==Icon::Stopwatch?stopwatch:
                             view.icon==Icon::Tomato?tomato:cup;
        frame.mask(mark,7,1,pomo?0:2,view.color);
        if (view.paused) for (int y=10;y<=13;++y) {
            frame.pixel(3,y,view.color); frame.pixel(5,y,view.color);
        }
        if (view.ready) {
            static const uint16_t play[12]={1,3,7,3,1};
            frame.mask(play,3,3,9,view.color);
        }
        TextRun digits(view.main,denki,maru);
        bool small=digits.width>42;
        if (small) digits=TextRun(view.main,nega,denki);
        digits.draw(frame,pomo?(small?8:4):(small?5:2),view.color,elapsed,10,true);
    } else if (!view.stampLine.empty() || !view.weatherKind.empty()) {
        int left=view.weatherKind.empty()?0:11;
        TextRun value(view.main,denki,maru);
        int finish=value.readTime(52-left);
        int read=std::max(3600,finish);
        int cycle=read+(view.stampLine.empty()?0:3000);
        int phase=int(elapsed%cycle);
        if (phase<read) {
            value.draw(frame,2,view.color,std::min(phase,finish-1),left);
            if (phase>=finish) frame.refreshAfter=std::numeric_limits<int>::max();
            frame.wake(read-phase);
            if (left) {
                if (view.automatic && phase<120) {
                    int shift=phase<60?2:1;
                    for (int y=0;y<16;++y) for (int x=51;x>=left;--x) {
                        size_t pos=(y*52+x)*3;
                        for (int k=0;k<3;++k)
                            frame.pixels[pos+k]=x-left>=shift?frame.pixels[pos+k-shift*3]:0;
                    }
                    frame.wake(60-phase%60);
                }
                weatherMark(frame,view.weatherKind,blue);
            }
        }
        else {
            line(frame,view.stampLine,nega,denki,0,amber);
            line(frame,view.sub,nega,denki,8,ivory);
            frame.wake(read+3000-phase);
        }
        if (left) frame.advanceAfter=cycle;
    } else if (view.compact) {
        line(frame,view.main,nega,denki,0,view.color,elapsed);
        line(frame,view.sub,nega,denki,8,ivory,elapsed);
    } else line(frame,view.main,denki,maru,2,view.color,elapsed);
    if (view.gauge>=0) frame.bar(15,view.gauge,view.color);
    if (view.weekday>=0) {
        static const uint32_t kanji[]={U'月',U'火',U'水',U'木',U'金',U'土',U'日'};
        const Glyph* dayGlyph=denki.find(kanji[view.weekday]);
        if (dayGlyph) frame.glyph(*dayGlyph,52-dayGlyph->width,2,green);
        for (int day=0;day<7;++day) {
            uint32_t color=day==view.weekday?green:0x172822;
            for (int x=2+day*7;x<2+day*7+6;++x)
                for (int y=14;y<=15;++y) frame.pixel(x,y,color);
        }
    }
    return frame;
}
}
