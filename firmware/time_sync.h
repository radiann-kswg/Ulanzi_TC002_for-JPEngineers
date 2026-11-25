#pragma once
#include "calendar.h"
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
#include <array>
#include <cstdint>
#include <ctime>

namespace tc {
using NtpPacket = std::array<uint32_t, 12>;
inline bool ntpTime(const NtpPacket& request, const NtpPacket& reply, timespec& result) {
    const uint32_t header = ntohl(reply[0]);
    const unsigned flags = header >> 24, version = (flags >> 3) & 7, stratum = (header >> 16) & 255;
    if ((flags >> 6) == 3 || version < 3 || version > 4 || (flags & 7) != 4 ||
        stratum < 1 || stratum > 15 || reply[6] != request[10] || reply[7] != request[11] ||
        (!reply[10] && !reply[11])) return false;
    // Unsigned subtraction unfolds the 2036 NTP rollover into the current Unix era.
    const uint32_t epoch = ntohl(reply[10]) - 2208988800u;
    if (!usableEpoch(epoch)) return false;
    result.tv_sec = epoch;
    result.tv_nsec = (uint64_t(ntohl(reply[11])) * 1000000000u) >> 32;
    return true;
}

inline bool syncNetworkTime() {
    addrinfo hints{}, *addresses = nullptr;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_DGRAM;
    if (getaddrinfo("ntp.nict.jp", "123", &hints, &addresses) != 0) return false;
    bool synced = false;
    for (auto* address = addresses; address && !synced; address = address->ai_next) {
        const int fd = socket(address->ai_family, address->ai_socktype, address->ai_protocol);
        if (fd < 0) continue;
        timeval timeout{2, 0};
        NtpPacket request{}, reply{};
        timespec sent{}, received{};
        clock_gettime(CLOCK_REALTIME, &sent);
        request[0] = htonl(0x23000000u);  // v4 client
        request[10] = htonl(uint32_t(sent.tv_sec) + 2208988800u);
        request[11] = htonl(uint32_t((uint64_t(sent.tv_nsec) << 32) / 1000000000u));
        if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) == 0 &&
            connect(fd, address->ai_addr, address->ai_addrlen) == 0 &&
            send(fd, request.data(), sizeof(request), 0) == sizeof(request) &&
            recv(fd, reply.data(), sizeof(reply), 0) == sizeof(reply) &&
            ntpTime(request, reply, received)) {
            synced = clock_settime(CLOCK_REALTIME, &received) == 0;
        }
        close(fd);
    }
    freeaddrinfo(addresses);
    return synced;
}
}
