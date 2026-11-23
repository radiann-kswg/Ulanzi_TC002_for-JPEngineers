#include "../../firmware/screen.h"
#include <cassert>
using namespace tc;

Layout sample(Clock& clock,int service,int page,const std::string& text,bool stale=false) {
    clock.nav.category=service; clock.nav.page[service]=page; clock.selection=0;
    clock.feed.generated=100000;
    clock.feed.pages[service][page]={{100000,text,stale}};
    return screen(clock,0,100000);
}
int main() {
    Clock clock;
    for (int c=0;c<3;++c) for (int p=0;p<8;++p) {
        auto v=sample(clock,c,p,"確認");
        assert(v.service==c && v.servicePage==p && !v.menu);
    }
    auto status=sample(clock,0,2,"failure nightly / release");
    assert(DevReading(status).mark==Symbol::Cross && DevReading(status).text=="失敗 nightly / release");
    auto review=sample(clock,0,5,"自分 承認済 テスト");
    assert(DevReading(review).mark==Symbol::Check);
    assert(ticketTitle("草稿 release-tools#421 配布準備")=="草稿 #421 配布準備 / release-tools");
    assert(ticketTitle("Issue通知 #421 配布準備")=="Issue通知 #421 配布準備");
    auto AI=sample(clock,1,4,"確認分 作業 1284 待ち 0");
    auto counts=DevReading(AI);
    assert(counts.pairedCounts && counts.partial && counts.upper=="1284" && counts.lower=="0");
    assert(!DevReading(sample(clock,1,4,"Cowork 未取得")).pairedCounts);
    auto next=sample(clock,2,1,"11/30 09:05 朝の確認");
    auto agenda=DevReading(next);
    assert(agenda.date=="11/30" && agenda.time=="09:05" && agenda.text=="朝の確認");
    auto usage=DevReading(sample(clock,2,6,"残 5h 100% / 7d 0%"));
    assert(usage.upper=="5h 100%" && usage.lower=="7d 0%");
    assert(DevReading(sample(clock,0,6,"残 0%")).remainingBar==0);
    assert(DevReading(sample(clock,0,6,"残 72.5%")).remainingBar==29);
    assert(DevReading(sample(clock,0,6,"残 取得不可")).remainingBar==-1);
    assert(DevReading(sample(clock,0,6,"追加 取得不可")).mark==Symbol::Cost);
    assert(DevReading(sample(clock,1,2,"failure 私のタスク")).text=="failure 私のタスク");

    Glyph question{'?',5,4,{7,5,7},0};
    Font font{&question,1};
    auto pr=sample(clock,0,0,"build/release/日本語の長いブランチ名#123");
    auto start=paint(pr,font,font,font,0), step=paint(pr,font,font,font,1000);
    assert(start.refreshAfter==1000);
    for (int y=0;y<16;++y) for (int x=0;x<51;++x) {
        int pos=(52*y+x)*3;
        for(int k=0;k<3;++k)
            assert(step.pixels[pos+k]==start.pixels[pos+k+(x>=12?3:0)]);
    }
    auto shortName=sample(clock,1,3,"A");
    assert(paint(shortName,font,font,font,0).refreshAfter==std::numeric_limits<int>::max());
    auto battery=sample(clock,0,7,"");
    auto unknown=paint(battery,font,font,font,0);
    assert(unknown.pixels[(15*52+12)*3]==0);
    clock.battery=0;
    auto emptyBattery=paint(screen(clock,0,100000),font,font,font,0);
    assert(emptyBattery.pixels[(15*52+12)*3]==0x24);
    auto stale=sample(clock,2,2,"長いセッションが通信断の時も最後まで読める",true);
    int read=TextRun(stale.main,font,font).readTime(40);
    assert(read>3600);
    auto reading=paint(stale,font,font,font,read-1), stamp=paint(stale,font,font,font,read);
    assert(reading.pixels!=stamp.pixels && !stale.stampLine.empty());
    auto time=paint(next,font,font,font,0), title=paint(next,font,font,font,2400);
    assert(time.refreshAfter==2400 && time.pixels!=title.pixels);
    clock.nav.level=Level::Category;
    auto menu=screen(clock,0,100000);
    assert(menu.menu && menu.servicePage==-1);
    clock.nav.level=Level::Menu;
    menu=screen(clock,0,100000);
    assert(menu.menu && menu.servicePage==2);
}
