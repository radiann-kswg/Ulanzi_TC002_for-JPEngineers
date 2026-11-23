#include "../../firmware/screen.h"
#include <cstdio>
#include <fstream>
using namespace tc;
int main() {
    Clock clock;
    std::ifstream input("/tmp/tc002-dev.feed");
    if (!readFeed(input,clock.feed) || !clock.feed.hasLocation) return 1;
    time_t now=time(nullptr);
    if (std::abs(int64_t(now)-clock.feed.generated)>90) return 2;
    clock.nav.category=3; clock.nav.page[3]=3;
    if (clock.feed.pages[3][3].empty() || screen(clock,0,now).main=="未取得") return 3;
    // Independent of this account's ownership, sessions, quotas and current weather values.
    if (screen(clock,3500,clock.feed.generated+91).sub.empty()) return 4;
    const auto& kinds=clock.feed.weatherKinds;
    if (std::find(kinds.begin(),kinds.end(),"place")==kinds.end()) return 5;
    return 0;
}
