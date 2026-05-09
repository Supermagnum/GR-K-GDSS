// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_LINHTPTTSOURCE_HPP
#define GNURADIO4_KGDSS_LINHTPTTSOURCE_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Value.hpp>
#include <gnuradio-4.0/annotated.hpp>

#include <atomic>
#include <cstddef>
#include <deque>
#include <iostream>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>

#ifdef GR_K_GDSS4_HAVE_ZMQ
#include <zmq.h>
#endif

namespace gnuradio4::kgdss {

GR_REGISTER_BLOCK(gnuradio4::kgdss::LinhtPttSource)

struct LinhtPttSource : gr::Block<LinhtPttSource, gr::Resampling<1UL, 1UL, true>, gr::NoTagPropagation> {
    using Description = gr::Doc<"Subscribe to LinHT PTT ZeroMQ endpoint (UTF-8 ptt_on / ptt_off) and emit gr::pmt "
                               "dict messages on ptt_out with key ptt (bool). No stream ports: call work() / "
                               "scheduler invokes processOne() to drain ZMQ asynchronously filled queue.">;

    gr::MsgPortOut                     ptt_out{};
    gr::Annotated<std::string, "ptt_endpoint", gr::Doc<"ZMQ SUB connect address (e.g. ipc:///tmp/linht_ptt)">> ptt_endpoint =
        std::string("ipc:///tmp/linht_ptt");
    gr::Annotated<std::string, "on_message", gr::Doc<"String that means PTT asserted">>  on_message  = std::string("ptt_on");
    gr::Annotated<std::string, "off_message", gr::Doc<"String that means PTT released">> off_message = std::string("ptt_off");

    GR_MAKE_REFLECTABLE(LinhtPttSource, ptt_out, ptt_endpoint, on_message, off_message);

    mutable std::mutex      _qmtx{};
    std::deque<bool>        _pendingPtt{};
    std::atomic<bool>       _zmqStop{ false };
    std::thread             _zmqThread{};
#ifdef GR_K_GDSS4_HAVE_ZMQ
    void* _zmqCtx{ nullptr };
    void* _zmqSock{ nullptr };
    std::string _connectUrl{};
    std::string _onStr{};
    std::string _offStr{};
#endif

    void pushPtt(bool v) noexcept {
        std::lock_guard lk(_qmtx);
        _pendingPtt.push_back(v);
    }

    /** Test/telemetry: queued PTT states not yet emitted on ptt_out. */
    [[nodiscard]] std::size_t pendingPttCountForTesting() const noexcept {
        std::lock_guard lk(_qmtx);
        return _pendingPtt.size();
    }

    static void emitPttOut(gr::MsgPortOut& port, bool on) noexcept {
        gr::Message msg;
        msg.cmd = gr::message::Command::Notify;
        gr::property_map pm;
        pm[gr::convert_string_domain(std::string_view("ptt"))] = gr::pmt::Value(on);
        msg.data                                               = std::move(pm);
        auto w = port.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
        if (w.size() >= 1UZ) {
            w[0] = std::move(msg);
            w.publish(1UZ);
        }
    }

    void processOne() noexcept {
        std::vector<bool> batch;
        {
            std::lock_guard lk(_qmtx);
            batch.assign(_pendingPtt.begin(), _pendingPtt.end());
            _pendingPtt.clear();
        }
        for (const bool v : batch) {
            emitPttOut(ptt_out, v);
        }
    }

    void start() noexcept {
#ifdef GR_K_GDSS4_HAVE_ZMQ
        _zmqStop.store(false, std::memory_order_release);
        _connectUrl = ptt_endpoint.value;
        _onStr      = on_message.value;
        _offStr     = off_message.value;
        _zmqCtx     = zmq_ctx_new();
        if (_zmqCtx == nullptr) {
            std::cerr << "LinhtPttSource: zmq_ctx_new failed\n";
            return;
        }
        _zmqSock = zmq_socket(_zmqCtx, ZMQ_SUB);
        if (_zmqSock == nullptr) {
            std::cerr << "LinhtPttSource: zmq_socket failed\n";
            zmq_ctx_term(_zmqCtx);
            _zmqCtx = nullptr;
            return;
        }
        zmq_setsockopt(_zmqSock, ZMQ_SUBSCRIBE, "", 0);
        if (zmq_connect(_zmqSock, _connectUrl.c_str()) != 0) {
            std::cerr << "LinhtPttSource: zmq_connect failed for " << _connectUrl << "\n";
            zmq_close(_zmqSock);
            zmq_ctx_term(_zmqCtx);
            _zmqSock = nullptr;
            _zmqCtx  = nullptr;
            return;
        }
        _zmqThread = std::thread([this] {
            while (!_zmqStop.load(std::memory_order_acquire)) {
                char    buf[256];
                const int n = zmq_recv(_zmqSock, buf, static_cast<int>(sizeof(buf) - 1), ZMQ_DONTWAIT);
                if (n > 0) {
                    buf[n] = '\0';
                    const std::string_view sv(buf);
                    if (sv == std::string_view(_onStr)) {
                        pushPtt(true);
                    } else if (sv == std::string_view(_offStr)) {
                        pushPtt(false);
                    }
                } else {
                    std::this_thread::sleep_for(std::chrono::milliseconds(1));
                }
            }
        });
#else
        static std::atomic<bool> once{ false };
        if (!once.exchange(true)) {
            std::cerr << "LinhtPttSource: built without libzmq (install libzmq / pkg-config libzmq); "
                         "PTT forwarding disabled\n";
        }
#endif
    }

    void stop() noexcept {
#ifdef GR_K_GDSS4_HAVE_ZMQ
        _zmqStop.store(true, std::memory_order_release);
        if (_zmqThread.joinable()) {
            _zmqThread.join();
        }
        if (_zmqSock != nullptr) {
            zmq_close(_zmqSock);
            _zmqSock = nullptr;
        }
        if (_zmqCtx != nullptr) {
            zmq_ctx_term(_zmqCtx);
            _zmqCtx = nullptr;
        }
#endif
    }
};

} // namespace gnuradio4::kgdss

#endif
