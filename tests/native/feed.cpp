#include "../../firmware/feed.h"
#include <cassert>
#include <sstream>
int main() {
    tc::Feed f;
    std::istringstream ok("TC002/1\nat\t123\nplace\t35\t139\t東京\nrow\t2\t1\t0\t未取得\nevent\t125\tid\t予定\nEND\n");
    assert(tc::readFeed(ok,f) && f.events.size()==1 && f.pages[2][1][0].stamp==0);
    for (auto text : {"row\t0\t8\t1\tbad","place\tnan\t99\ta","row\t-1\t0\t1\tbad","END\nextra"}) {
        std::istringstream bad(std::string("TC002/1\nat\t400\n")+text+"\nEND\n");
        assert(!tc::readFeed(bad,f) && f.generated==123);
    }
    std::istringstream partial("TC002/1\nat\t150\nEND\n");
    assert(tc::readFeed(partial,f) && f.place=="東京" && f.latitude==35);
}
