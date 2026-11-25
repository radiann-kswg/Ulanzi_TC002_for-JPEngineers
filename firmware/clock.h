#pragma once
#include "calendar.h"
#include "display.h"
#include "feed.h"
#include "timing.h"
#include <deque>
#include <set>

namespace tc {
enum class Sound { None, Tick, Minute, Hour, Midnight, Rest, Resume, Alarm,
                   Rotate, Enter, Button, Silence };
inline const char* categoryName(int category) {
    static const char* names[]={"GitHub","Claude","Codex","時計"}; return names[category];
}
inline const char* pageName(int category,int page) {
    static const char* github[]={"PR一覧","PR残件","Actions","Issue一覧","Issue残件","レビュー","利用残量","電池・IP"};
    static const char* ai[]={"予定通知","次の予定","作業状況","入力待ち","件数","直近完了","利用残量","電池・IP"};
    static const char* clock[]={"世界時計","時刻","暦","天気","ポモドーロ","タイマー","ストップ","電池・IP"};
    return (category==3?clock:category==0?github:ai)[page];
}
struct Clock {
    Navigation nav;
    World world;
    Timer timer;
    Interval pomo{pomoMinFocus,10}, busy{30,5};
    Elapsed stopwatch;
    int volume=3, battery=-1;
    std::string ip;
    Feed feed;
    size_t selection=0;
    Millis entered=0, noticeUntil=0;
    Millis autoAt=-1;
    std::string notice;
    int noticeService=-1,noticePage=-1;
    bool popupActive=false;
    std::set<std::string> handled;
    std::deque<std::string> order;
    struct Popup { std::string text; int service,page; };
    std::deque<Popup> pending;
    std::array<std::deque<Row>,3> dueHistory;
    int64_t checkedAt=-1;
    Millis lastAlarm=-10000, lastAdvance=0;
    int64_t lastSecond=-1;
    bool wasRest[2]={false,false};
    bool alarmActive=false;

    void intervalKey(Interval& cycle,bool isBusy,Action a,Millis now) {
        if (!cycle.elapsed.running && cycle.elapsed.value(now)==0) {
            if (a==Action::Minus) {
                if (isBusy) cycle.focus=cycle.focus==30?45:cycle.focus==45?60:30;
                else cycle.focus=pomoFocusMinutes(cycle.focus+pomoFocusStep);
            }
            if (a==Action::Plus) cycle.rest=cycle.rest==5?10:cycle.rest==10?15:5;
            if (a==Action::Plus || a==Action::Minus) {
                notice=std::string(a==Action::Plus?"休憩 ":"活動 ")+
                    std::to_string(a==Action::Plus?cycle.rest:cycle.focus)+"分";
                noticeUntil=now+1200;
            }
        }
        cycle.command(a,now);
    }

    Sound command(Action a,Millis now) {
        if (a==Action::None) return Sound::None;
        noticeUntil=0;
        popupActive=false;
        noticeService=noticePage=-1;
        if (a==Action::Louder || a==Action::Quieter) {
            volume=clamp(volume+(a==Action::Louder?1:-1),0,6);
            notice="音量 "+std::to_string(volume); noticeUntil=now+900;
            return Sound::Button;
        }
        if (nav.navigate(a)) {
            entered=now;
            if (a!=Action::Busy) selection=0;
            return a==Action::Previous || a==Action::Next ? Sound::Rotate : Sound::Enter;
        }
        if (nav.busy) { intervalKey(busy,true,a,now); return Sound::Button; }
        if (nav.level!=Level::Screen) return Sound::None;
        const int p=nav.page[nav.category];
        if (nav.category==3 && p==0) world.command(a);
        if (nav.category==3 && p==4) intervalKey(pomo,false,a,now);
        if (nav.category==3 && p==5) {
            const bool silencing=timer.left(now)<=0 && (a==Action::Center || a==Action::HoldCenter);
            timer.command(a,now);
            if (silencing) { alarmActive=false; return Sound::Silence; }
        }
        if (nav.category==3 && p==6) {
            if (a==Action::Center) stopwatch.toggle(now);
            if (a==Action::HoldCenter) stopwatch.reset();
        }
        bool browse = a==Action::Next || a==Action::Previous;
        if (p==7 || nav.category!=3 || p==2 || p==3)
            browse = browse || a==Action::Plus || a==Action::Minus || a==Action::Center;
        if (browse) {
            size_t count=itemCount();
            const bool back=a==Action::Previous || a==Action::Minus;
            selection=(selection%count+(back?count-1:1))%count;
            entered=now;
        }
        return Sound::Button;
    }
    size_t itemCount() const {
        int c=nav.category,p=nav.page[c];
        if (p==7) return 2;
        if (c<3 && p==6 && feed.pages[c][p].empty()) return 2;
        if (c==3 && p==2) return 3;
        if (c==1 || c==2) {
            if (p==0 || p==1) return std::max<size_t>(1,scheduleRows(c,p,checkedAt).size());
        }
        return std::max<size_t>(1,feed.pages[c][p].size());
    }
    bool autoBrowse(Millis now) {
        if (nav.busy || nav.level!=Level::Screen || nav.category!=3 ||
            (nav.page[3]!=2 && nav.page[3]!=3) || itemCount()<2) return false;
        selection=(selection+1)%itemCount();
        entered=autoAt=now;
        return true;
    }

    std::vector<Row> scheduleRows(int c,int p,time_t utc) const {
        std::vector<Row> rows;
        std::set<std::string> seen;
        const auto& cached=feed.pages[c][p];
        const bool offline=int64_t(utc)-feed.generated>90;
        if (p==0) {
            for (const Row& r:dueHistory[c]) { rows.push_back(r); seen.insert(r.text); }
            for (const Row& r:cached)
                if ((rows.empty() || r.text!="通知なし") && seen.insert(r.text).second) rows.push_back(r);
        } else if (offline) {
            std::string prefix="schedule-"+std::to_string(c)+"-";
            for (const Notice& e:feed.events) {
                if (e.due<=utc || e.id.compare(0,prefix.size(),prefix)!=0 ||
                    !seen.insert(e.id.substr(0,e.id.rfind('-'))).second) continue;
                rows.push_back({feed.generated,dated(e.due)+" "+e.text,true});
            }
            if (rows.empty() && feed.generated) rows.push_back({feed.generated,"次は未取得",true});
        } else rows=cached;
        return rows;
    }

    static std::string dated(time_t epoch) {
        auto t=localFields(epoch); char buf[32];
        snprintf(buf,sizeof buf,"%02d/%02d %02d:%02d",t.tm_mon+1,t.tm_mday,t.tm_hour,t.tm_min);
        return buf;
    }

    const Elapsed& tickCounter() const {
        // Follow the visible counter first. Background counters share one audible beat.
        if (nav.busy && busy.elapsed.running) return busy.elapsed;
        if (!nav.busy && nav.level==Level::Screen && nav.category==3) {
            if (nav.page[3]==4 && pomo.elapsed.running) return pomo.elapsed;
            if (nav.page[3]==6 && stopwatch.running) return stopwatch;
        }
        if (timer.elapsed.running) return timer.elapsed;
        if (busy.elapsed.running) return busy.elapsed;
        if (stopwatch.running) return stopwatch;
        return pomo.elapsed;
    }

    Sound advance(Millis now,time_t utc) {
        Sound cue=Sound::None;
        if (!nav.busy && nav.category==3 && nav.level==Level::Screen && nav.page[3]==1) {
            if (lastSecond>=0 && utc==lastSecond+1) {
                std::tm t=localFields(utc);
                cue=t.tm_sec?Sound::Tick:t.tm_min?Sound::Minute:t.tm_hour?Sound::Hour:Sound::Midnight;
            }
        } else if (tickCounter().crossedSecond(lastAdvance,now)) cue=Sound::Tick;
        lastAdvance=now;
        lastSecond=utc;
        Interval* cycles[]={&pomo,&busy};
        for (int i=0;i<2;++i) {
            bool rest=cycles[i]->resting(now);
            if (rest!=wasRest[i] && cycles[i]->elapsed.running)
                cue=rest?Sound::Rest:Sound::Resume;
            wasRest[i]=rest;
        }
        if (timer.elapsed.running && timer.left(now)<=0) {
            cue=(!alarmActive || now-lastAlarm>=2000)?Sound::Alarm:Sound::None;
            if (cue==Sound::Alarm) lastAlarm=now;
            alarmActive=true;
        } else alarmActive=false;

        if (checkedAt!=utc) for (const Notice& e: feed.events) {
            if (e.due>utc || int64_t(utc)-e.due>60 || !handled.insert(e.id).second) continue;
            order.push_back(e.id);
            if (order.size()>256) { handled.erase(order.front()); order.pop_front(); }
            Popup popup{e.text,-1,-1};
            if (e.text.find("PR ")==0 || e.text.find("PR通知 ")==0) popup={e.text,0,0};
            else if (e.text.find("Issue ")==0 || e.text.find("Issue通知 ")==0) popup={e.text,0,3};
            else if (e.text.find("失敗 ")==0 || e.text.find("復旧 ")==0) popup={e.text,0,2};
            for (int c=1;c<=2;++c) if (e.id.compare(0,11,"schedule-"+std::to_string(c)+"-")==0) {
                dueHistory[c].push_front({e.due,dated(e.due)+" "+e.text+" 予定",false});
                if (dueHistory[c].size()>32) dueHistory[c].pop_back();
                popup={"予定 "+e.text,c,0};
            }
            if (!nav.busy && pending.size()<12) pending.push_back(popup);
        }
        checkedAt=utc;
        if (nav.busy) pending.clear();
        if (!popupActive && now>=noticeUntil) nextPopup();
        return cue;
    }

    void nextPopup() {
        popupActive=!pending.empty() && !nav.busy && !alarmActive;
        if (popupActive) {
            const auto& popup=pending.front();
            notice=popup.text; noticeService=popup.service; noticePage=popup.page;
            pending.pop_front();
        }
    }
};
}
