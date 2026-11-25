#include "time_sync.h"
#include <cassert>

int main() {
    tc::NtpPacket sent{}, reply{};
    sent[10] = htonl(2208988800u);
    sent[11] = htonl(42);
    reply[6] = sent[10];
    reply[7] = sent[11];
    reply[0] = htonl(0x24010000u);
    reply[10] = htonl(1795585731u + 2208988800u);
    reply[11] = htonl(0x80000000u);
    timespec stamp{};
    assert(tc::ntpTime(sent, reply, stamp));
    assert(stamp.tv_sec == 1795585731 && stamp.tv_nsec == 500000000);
    reply[10] = htonl(2110000000u + 2208988800u);
    assert(tc::ntpTime(sent, reply, stamp) && stamp.tv_sec == 2110000000);
    reply[0] = htonl(0xe4010000u);
    assert(!tc::ntpTime(sent, reply, stamp));
    reply[0] = htonl(0x24000000u);
    assert(!tc::ntpTime(sent, reply, stamp));
    reply[0] = htonl(0x24010000u);
    ++reply[7];
    assert(!tc::ntpTime(sent, reply, stamp));
    assert(!tc::usableEpoch(600));
}
