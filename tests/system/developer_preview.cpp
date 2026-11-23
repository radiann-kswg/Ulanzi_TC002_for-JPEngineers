// Render synthetic data on the ARM target with the same fonts as the installed app.
#include "screen.h"
#include "fonts.h"
#include <cassert>
#include <fstream>
using namespace tc;

int main() {
    const time_t now=1795400016;
    const char* demo[3][7]={
        {"tools#42 配色調整","12件","failure build / main","desk#7 仕様確認","3件","依頼 tools#18 書体","残 72%"},
        {"11/23 08:30 朝の確認","11/24 09:30 朝の確認","手順整理","仕様確認","確認分 作業 2 待ち 1","文書更新","追加 2.00 USD"},
        {"11/23 09:00 配布準備","11/24 18:00 配布準備","実装中","承認待ち","作業 12 待ち 0","修正完了","残 5h 80% / 7d 42%"}
    };
    const char* stress[3][7]={
        {"release-engineering-for-production#2048 地域別天気予報の切り替えを確認する","1234567件",
         "timed_out compatibility-check / feature/自動計時","該当なし","0件","自分 変更依頼 test#1 長い説明","残 0%"},
        {"通知なし","11/30 23:59 月末締めの定期処理と利用状況の確認","Cowork 未取得","該当なし",
         "確認分 作業 1284 待ち 0","A","追加 取得不可"},
        {"次は未取得","予定なし","日本語とEnglishが混在する入力待ち対象の動作確認","X",
         "作業 0 待ち 0","プロジェクト内","残 10080m 0.25% / 43200m 100%"}
    };
    std::ofstream output("/tmp/tc002-views.rgb",std::ios::binary);
    if (!output) return 1;
    for (int hard=0;hard<2;++hard) for (int p=0;p<8;++p) for (int c=0;c<3;++c) {
        Clock clock;
        clock.nav.category=c; clock.nav.page[c]=p; clock.feed.generated=now;
        bool offline=hard && c==2 && p==2;
        if (offline) clock.feed.generated=now-91;
        if (p<7) clock.feed.pages[c][p].push_back({now-90,(hard?stress:demo)[c][p],hard && c==2 && p==2});
        else {
            clock.battery=hard?-1:85; clock.ip=hard?"":"203.0.113.42";
            clock.selection=c==1?1:0;
        }
        Layout view=screen(clock,0,now);
        int elapsed=!hard && c>0 && p==0?2400:0;
        if (offline) elapsed=std::max(3600,TextRun(view.main,denki,maru).readTime(developerWidth));
        auto frame=paint(view,denki,nega,maru,elapsed);
        if (offline) assert(frame.refreshAfter==3000 && view.stampLine.find("OFF ")==0);
        for (int y=0;y<16;++y) for (int x=10;x<=11;++x) for (int k=0;k<3;++k)
            assert(frame.pixels[3*(y*52+x)+k]==0);
        if (frame.refreshAfter==1000 && view.gauge<0) {
            auto next=paint(view,denki,nega,maru,elapsed+1000);
            for (int y=0;y<16;++y) for (int x=0;x<51;++x) for (int k=0;k<3;++k)
                assert(next.pixels[3*(y*52+x)+k]==frame.pixels[3*(y*52+x+(x>=12))+k]);
        }
        output.write(reinterpret_cast<const char*>(frame.pixels.data()),frame.pixels.size());
    }
    output.close();
    return output?0:2;
}
