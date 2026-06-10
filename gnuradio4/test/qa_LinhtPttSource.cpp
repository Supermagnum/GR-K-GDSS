// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Value.hpp>
#include <gnuradio-4.0/kgdss/LinhtPttSource.hpp>

#include <cstdint>
#include <string>
#include <thread>
#include <vector>

#ifdef GR_K_GDSS4_HAVE_ZMQ
#include <zmq.h>
#endif

using namespace boost::ut;

namespace {

struct PttRecorder : gr::Block<PttRecorder, gr::Resampling<1UL, 1UL, true>, gr::NoTagPropagation> {
    gr::MsgPortIn                 ptt_in{};
    std::vector<int>              recorded{};
    GR_MAKE_REFLECTABLE(PttRecorder, ptt_in);

    void processOne() noexcept {}

    void processMessages(gr::MsgPortIn& port, std::span<const gr::Message> messages) noexcept {
        if (std::addressof(port) != std::addressof(ptt_in)) {
            return;
        }
        for (const gr::Message& m : messages) {
            if (!m.data.has_value()) {
                continue;
            }
            const gr::property_map& pm = m.data.value();
            const std::pmr::string  k = gr::convert_string_domain(std::string_view("ptt"));
            const auto              it = pm.find(k);
            if (it == pm.end()) {
                continue;
            }
            if (const auto* b = it->second.get_if<bool>()) {
                recorded.push_back(*b ? 1 : 0);
            }
        }
    }
};

} // namespace

const suite<"LinhtPttSource"> LinhtPttSuite = [] {
    "start_stop_without_daemon_no_throw"_test = [] {
        gnuradio4::kgdss::LinhtPttSource block(gr::property_map{ { "name", std::string("ptt0") },
            { "ptt_endpoint", std::string("ipc:///tmp/nonexistent_linht_ptt_path_for_ut") } });
        block.init(std::make_shared<gr::Sequence>());
        block.start();
        block.stop();
    };

    "endpoint_reflected_after_init"_test = [] {
        gnuradio4::kgdss::LinhtPttSource block(gr::property_map{ { "name", std::string("ptt1") },
            { "ptt_endpoint", std::string("inproc://ptt_ut_endp") } });
        block.init(std::make_shared<gr::Sequence>());
        expect(eq(block.ptt_endpoint.value, std::string("inproc://ptt_ut_endp")));
    };

#ifdef GR_K_GDSS4_HAVE_ZMQ
    "zmq_ptt_on_off_dict"_test = [] {
        const int              port = 26055;
        const std::string      url = std::string("tcp://127.0.0.1:") + std::to_string(port);
        gnuradio4::kgdss::LinhtPttSource src(gr::property_map{ { "name", std::string("ptt_z") },
            { "ptt_endpoint", url } });
        src.init(std::make_shared<gr::Sequence>());
        PttRecorder                      rec(gr::property_map{ { "name", std::string("rec") } });
        rec.init(std::make_shared<gr::Sequence>());
        expect(src.ptt_out.connect(rec.ptt_in).has_value());

        void* ctx = zmq_ctx_new();
        expect(ctx != nullptr);
        void* pub = zmq_socket(ctx, ZMQ_PUB);
        expect(pub != nullptr);
        expect(zmq_bind(pub, url.c_str()) == 0);
        std::this_thread::sleep_for(std::chrono::milliseconds(20));

        src.start();
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        const char m1[] = "ptt_on";
        expect(zmq_send(pub, m1, sizeof(m1) - 1U, 0) >= 0);
        for (int i = 0; i < 500; ++i) {
            if (src.pendingPttCountForTesting() > 0UZ) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        expect(src.pendingPttCountForTesting() >= 1UZ);
        for (int i = 0; i < 80; ++i) {
            src.processOne();
            src.processScheduledMessages();
            rec.processOne();
            rec.processScheduledMessages();
            if (!rec.recorded.empty()) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        expect((rec.recorded.size() == 1UZ) && (rec.recorded[0] == 1));

        const char m2[] = "ptt_off";
        rec.recorded.clear();
        expect(zmq_send(pub, m2, sizeof(m2) - 1U, 0) >= 0);
        for (int i = 0; i < 500; ++i) {
            if (src.pendingPttCountForTesting() > 0UZ) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
        expect(src.pendingPttCountForTesting() >= 1UZ);
        for (int i = 0; i < 80; ++i) {
            src.processOne();
            src.processScheduledMessages();
            rec.processOne();
            rec.processScheduledMessages();
            if (!rec.recorded.empty()) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        expect((rec.recorded.size() == 1UZ) && (rec.recorded[0] == 0));

        rec.recorded.clear();
        const char m3[] = "unknown";
        expect(zmq_send(pub, m3, sizeof(m3) - 1U, 0) >= 0);
        for (int i = 0; i < 40; ++i) {
            src.processOne();
            src.processScheduledMessages();
            rec.processOne();
            rec.processScheduledMessages();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        expect(eq(rec.recorded.size(), 0UZ));

        src.stop();
        zmq_close(pub);
        zmq_ctx_term(ctx);
    };
#endif
};

int main() {
    return boost::ut::cfg<boost::ut::override>.run();
}
