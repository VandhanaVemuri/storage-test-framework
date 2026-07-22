// storage_test_cli
//
// Reads one command per line from stdin, executes it against a
// SimulatedDevice instance, and writes one response line to stdout.
// This line protocol stands in for the interface a real automation
// framework would use to drive a firmware test bench (e.g. over a
// vendor SDK, a serial link, or an NVMe passthrough ioctl) - the
// Python side (device_client.py) treats this process as the "DUT".
//
// Command format (space-separated, uppercase op name first):
//   WRITE <lba> <hex_data>
//   READ <lba> <length>
//   FLUSH
//   TRIM <lba> <length>
//   GET_LOG_PAGE
//   IDENTIFY
//   INJECT_ERROR BAD_BLOCK <lba>
//   INJECT_ERROR POWER_LOSS
//   EXIT
//
// Response format:
//   <STATUS> [data=<hex_or_kv>] [msg=<text>] latency_us=<n>
#include "device.hpp"
#include <iostream>
#include <sstream>
#include <chrono>
#include <vector>
#include <string>

static std::vector<std::string> split(const std::string& line) {
    std::istringstream iss(line);
    std::vector<std::string> tokens;
    std::string tok;
    while (iss >> tok) tokens.push_back(tok);
    return tokens;
}

static void printResult(const OpResult& r, long long latencyUs) {
    std::cout << statusToString(r.status);
    if (!r.data.empty()) std::cout << " data=" << r.data;
    if (!r.message.empty()) std::cout << " msg=" << r.message;
    std::cout << " latency_us=" << latencyUs << "\n";
    std::cout.flush();
}

int main() {
    SimulatedDevice device;
    std::string line;

    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        auto tokens = split(line);
        if (tokens.empty()) continue;

        const std::string& op = tokens[0];
        auto start = std::chrono::steady_clock::now();
        OpResult result{OpStatus::ERR_UNKNOWN_OP, "", "unrecognized op"};

        try {
            if (op == "WRITE" && tokens.size() >= 3) {
                result = device.write((uint32_t)std::stoul(tokens[1]), tokens[2]);
            } else if (op == "READ" && tokens.size() >= 3) {
                result = device.read((uint32_t)std::stoul(tokens[1]), (uint32_t)std::stoul(tokens[2]));
            } else if (op == "FLUSH") {
                result = device.flush();
            } else if (op == "TRIM" && tokens.size() >= 3) {
                result = device.trim((uint32_t)std::stoul(tokens[1]), (uint32_t)std::stoul(tokens[2]));
            } else if (op == "GET_LOG_PAGE") {
                result = device.getLogPage();
            } else if (op == "IDENTIFY") {
                result = device.identify();
            } else if (op == "INJECT_ERROR" && tokens.size() >= 2 && tokens[1] == "BAD_BLOCK" && tokens.size() >= 3) {
                result = device.injectBadBlock((uint32_t)std::stoul(tokens[2]));
            } else if (op == "INJECT_ERROR" && tokens.size() >= 2 && tokens[1] == "POWER_LOSS") {
                result = device.injectPowerLoss();
            } else if (op == "EXIT") {
                break;
            } else {
                result = {OpStatus::ERR_BAD_ARGS, "", "malformed or unknown command: " + line};
            }
        } catch (const std::exception& e) {
            result = {OpStatus::ERR_BAD_ARGS, "", std::string("exception: ") + e.what()};
        }

        auto end = std::chrono::steady_clock::now();
        long long latencyUs = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
        printResult(result, latencyUs);
    }

    return 0;
}
