#include "device.hpp"
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <numeric>

namespace {

std::string bytesToHex(const std::vector<uint8_t>& bytes) {
    std::ostringstream oss;
    for (uint8_t b : bytes) {
        oss << std::hex << std::setw(2) << std::setfill('0') << (int)b;
    }
    return oss.str();
}

bool hexToBytes(const std::string& hex, std::vector<uint8_t>& out) {
    if (hex.size() % 2 != 0) return false;
    out.clear();
    out.reserve(hex.size() / 2);
    for (size_t i = 0; i < hex.size(); i += 2) {
        std::string byteStr = hex.substr(i, 2);
        try {
            out.push_back((uint8_t)std::stoi(byteStr, nullptr, 16));
        } catch (...) {
            return false;
        }
    }
    return true;
}

} // namespace

std::string statusToString(OpStatus s) {
    switch (s) {
        case OpStatus::OK: return "OK";
        case OpStatus::ERR_BAD_BLOCK: return "ERR_BAD_BLOCK";
        case OpStatus::ERR_OUT_OF_RANGE: return "ERR_OUT_OF_RANGE";
        case OpStatus::ERR_NO_SPARE_BLOCKS: return "ERR_NO_SPARE_BLOCKS";
        case OpStatus::ERR_UNKNOWN_OP: return "ERR_UNKNOWN_OP";
        case OpStatus::ERR_BAD_ARGS: return "ERR_BAD_ARGS";
    }
    return "ERR_UNKNOWN_OP";
}

SimulatedDevice::SimulatedDevice(uint32_t numUserBlocks, uint32_t numSpareBlocks, uint32_t blockSize)
    : numUserBlocks_(numUserBlocks),
      numSpareBlocks_(numSpareBlocks),
      blockSize_(blockSize),
      nextSpareBlock_(numUserBlocks) {
    storage_.assign((size_t)(numUserBlocks_ + numSpareBlocks_) * blockSize_, 0);
    wearCount_.assign(numUserBlocks_ + numSpareBlocks_, 0);
}

bool SimulatedDevice::inRange(uint32_t lba) const {
    return lba < numUserBlocks_;
}

uint32_t SimulatedDevice::resolveLba(uint32_t lba) {
    auto it = remapTable_.find(lba);
    if (it != remapTable_.end()) return it->second;
    if (badBlocks_.count(lba)) {
        // Needs a remap but doesn't have one yet - caller allocates.
        return lba; // signal: caller checks badBlocks_ again after this
    }
    return lba;
}

void SimulatedDevice::commitBlock(uint32_t physicalBlock, const std::vector<uint8_t>& data) {
    std::copy(data.begin(), data.end(), storage_.begin() + (size_t)physicalBlock * blockSize_);
    wearCount_[physicalBlock]++;
}

OpResult SimulatedDevice::write(uint32_t lba, const std::string& hexData) {
    if (!inRange(lba)) return {OpStatus::ERR_OUT_OF_RANGE, "", "lba out of range"};

    std::vector<uint8_t> data;
    if (!hexToBytes(hexData, data)) return {OpStatus::ERR_BAD_ARGS, "", "invalid hex payload"};
    if (data.size() > blockSize_) return {OpStatus::ERR_BAD_ARGS, "", "payload exceeds block size"};
    data.resize(blockSize_, 0); // zero-pad to full block, like real block writes

    uint32_t physicalBlock = lba;
    std::string message;

    if (badBlocks_.count(lba)) {
        auto it = remapTable_.find(lba);
        if (it != remapTable_.end()) {
            physicalBlock = it->second;
        } else {
            if (nextSpareBlock_ >= numUserBlocks_ + numSpareBlocks_) {
                return {OpStatus::ERR_NO_SPARE_BLOCKS, "", "spare area exhausted"};
            }
            physicalBlock = nextSpareBlock_++;
            remapTable_[lba] = physicalBlock;
            message = "REMAPPED";
        }
    }

    // Writes land in the shadow (uncommitted) area first. They are visible
    // to reads immediately (read-after-write) but are only durable across a
    // simulated power loss once FLUSH has been called - this mirrors the
    // real write-then-flush durability contract of block storage devices.
    shadow_[physicalBlock] = data;
    return {OpStatus::OK, "", message};
}

OpResult SimulatedDevice::read(uint32_t lba, uint32_t length) {
    if (!inRange(lba)) return {OpStatus::ERR_OUT_OF_RANGE, "", "lba out of range"};
    if (length == 0 || length > blockSize_) return {OpStatus::ERR_BAD_ARGS, "", "invalid length"};

    uint32_t physicalBlock = lba;
    auto remapIt = remapTable_.find(lba);
    if (remapIt != remapTable_.end()) physicalBlock = remapIt->second;

    std::vector<uint8_t> out;
    auto shadowIt = shadow_.find(physicalBlock);
    if (shadowIt != shadow_.end()) {
        out.assign(shadowIt->second.begin(), shadowIt->second.begin() + length);
    } else {
        auto begin = storage_.begin() + (size_t)physicalBlock * blockSize_;
        out.assign(begin, begin + length);
    }
    return {OpStatus::OK, bytesToHex(out), ""};
}

OpResult SimulatedDevice::flush() {
    for (auto& kv : shadow_) {
        commitBlock(kv.first, kv.second);
    }
    size_t n = shadow_.size();
    shadow_.clear();
    return {OpStatus::OK, "", "committed_" + std::to_string(n) + "_blocks"};
}

OpResult SimulatedDevice::trim(uint32_t lba, uint32_t length) {
    if (!inRange(lba) || !inRange(lba + length - 1)) {
        return {OpStatus::ERR_OUT_OF_RANGE, "", "trim range out of bounds"};
    }
    for (uint32_t i = 0; i < length; ++i) {
        uint32_t cur = lba + i;
        uint32_t physicalBlock = cur;
        auto remapIt = remapTable_.find(cur);
        if (remapIt != remapTable_.end()) physicalBlock = remapIt->second;
        shadow_.erase(physicalBlock);
        std::fill_n(storage_.begin() + (size_t)physicalBlock * blockSize_, blockSize_, 0);
    }
    return {OpStatus::OK, "", "trimmed_" + std::to_string(length) + "_blocks"};
}

OpResult SimulatedDevice::getLogPage() const {
    uint32_t total = numUserBlocks_ + numSpareBlocks_;
    uint32_t sum = std::accumulate(wearCount_.begin(), wearCount_.end(), 0u);
    uint32_t maxWear = *std::max_element(wearCount_.begin(), wearCount_.end());
    double avgWear = total > 0 ? (double)sum / total : 0.0;

    std::ostringstream oss;
    oss << "WEAR_AVG=" << std::fixed << std::setprecision(2) << avgWear
        << ",WEAR_MAX=" << maxWear
        << ",BAD_BLOCKS=" << badBlocks_.size()
        << ",SPARE_USED=" << (nextSpareBlock_ - numUserBlocks_)
        << ",SPARE_TOTAL=" << numSpareBlocks_;
    return {OpStatus::OK, oss.str(), ""};
}

OpResult SimulatedDevice::identify() const {
    std::ostringstream oss;
    oss << "MODEL=SIM-SSD-01,USER_BLOCKS=" << numUserBlocks_
        << ",SPARE_BLOCKS=" << numSpareBlocks_
        << ",BLOCK_SIZE=" << blockSize_;
    return {OpStatus::OK, oss.str(), ""};
}

OpResult SimulatedDevice::injectBadBlock(uint32_t lba) {
    if (!inRange(lba)) return {OpStatus::ERR_OUT_OF_RANGE, "", "lba out of range"};
    badBlocks_.insert(lba);
    return {OpStatus::OK, "", "marked_bad"};
}

OpResult SimulatedDevice::injectPowerLoss() {
    // Abruptly drop everything written since the last FLUSH - this is what
    // makes the power-loss test cases meaningful: any write the test issued
    // but never flushed should NOT survive, while anything flushed before
    // the power loss should read back unchanged.
    size_t lost = shadow_.size();
    shadow_.clear();
    return {OpStatus::OK, "", "lost_" + std::to_string(lost) + "_unflushed_blocks"};
}
