#pragma once
#include <cstdint>
#include <vector>
#include <string>
#include <unordered_map>
#include <unordered_set>

// Status codes returned by the simulated device. Mirrors the kind of
// coarse status/error reporting a real NVMe-style completion queue entry
// would carry (success vs. a small set of well-defined error classes).
enum class OpStatus {
    OK,
    ERR_BAD_BLOCK,
    ERR_OUT_OF_RANGE,
    ERR_NO_SPARE_BLOCKS,
    ERR_UNKNOWN_OP,
    ERR_BAD_ARGS
};

std::string statusToString(OpStatus s);

struct OpResult {
    OpStatus status;
    std::string data;     // hex-encoded payload (READ / GET_LOG_PAGE / IDENTIFY)
    std::string message;  // free-form extra info (e.g. "REMAPPED", "POWER_LOSS_LOST_1_BLOCK")
};

// SimulatedDevice models a small block device with just enough firmware-like
// behavior to make validation testing meaningful:
//  - per-block wear counters (SMART-style health reporting)
//  - bad-block detection + remap-to-spare-area (like real flash translation layers)
//  - a write-then-flush durability contract: writes are visible to reads
//    immediately (read-after-write), but are only guaranteed to survive a
//    simulated power loss once FLUSH has been called. This is the same
//    contract real SSDs make, and it's the behavior the power-loss test
//    cases in this project are designed to validate.
class SimulatedDevice {
public:
    explicit SimulatedDevice(uint32_t numUserBlocks = 960, uint32_t numSpareBlocks = 64, uint32_t blockSize = 512);

    OpResult write(uint32_t lba, const std::string& hexData);
    OpResult read(uint32_t lba, uint32_t length);
    OpResult flush();
    OpResult trim(uint32_t lba, uint32_t length);
    OpResult getLogPage() const;
    OpResult identify() const;

    // Test-only fault-injection hooks (not part of the "real" device API,
    // analogous to the fault-injection hooks storage test benches use to
    // exercise firmware error paths without needing real failing hardware).
    OpResult injectBadBlock(uint32_t lba);
    OpResult injectPowerLoss();

    uint32_t blockSize() const { return blockSize_; }

private:
    uint32_t numUserBlocks_;
    uint32_t numSpareBlocks_;
    uint32_t blockSize_;
    uint32_t nextSpareBlock_;

    std::vector<uint8_t> storage_;              // committed data, one blockSize_ chunk per block
    std::vector<uint32_t> wearCount_;            // per physical block
    std::unordered_set<uint32_t> badBlocks_;     // logical LBAs marked bad
    std::unordered_map<uint32_t, uint32_t> remapTable_; // bad logical LBA -> spare physical block
    std::unordered_map<uint32_t, std::vector<uint8_t>> shadow_; // uncommitted writes since last flush, keyed by physical block

    bool inRange(uint32_t lba) const;
    uint32_t resolveLba(uint32_t lba); // applies remap table, allocating a spare if needed
    void commitBlock(uint32_t physicalBlock, const std::vector<uint8_t>& data);
};
