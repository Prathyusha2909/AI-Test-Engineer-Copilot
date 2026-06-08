# Falcon-X Network Card Validation Specification

## Product Overview

Falcon-X is a dual-port 100 GbE network card for high-throughput storage and compute clusters. The card uses a PCIe Gen4 x16 host interface, an embedded firmware loader, packet buffer SRAM, PHY/SerDes lanes, and card-level telemetry for rail voltage and ASIC temperature.

## Functional Requirements

- The device shall enumerate as PCIe Gen4 x16 and expose control, telemetry, and DMA BARs.
- The DMA engine shall support host-to-card and card-to-host transfers with interrupt moderation.
- Firmware shall boot from primary image, validate signature, and rollback to a known-good image when validation fails.
- The traffic datapath shall sustain 100 GbE bidirectional throughput with packet loss below 0.01 percent under nominal temperature.
- The packet buffer manager shall tolerate burst traffic without unrecovered queue overflow or descriptor leaks.
- The PHY layer shall report CRC errors, link retrain events, and lane status.
- Thermal monitoring shall warn at 85 C and throttle before the ASIC exceeds 95 C.
- Reset handling shall support software reset, hot reset, and surprise link down recovery without requiring host reboot.

## Key Signals and Components

- PCIe reference clock
- PCIe completion timeout counter
- DMA descriptor ring occupancy
- Firmware boot-stage marker
- Packet queue depth
- PHY CRC counter
- ASIC temperature sensor
- Core voltage rail

## Acceptance Criteria

- Power-on validation passes across 25 cold boots.
- PCIe enumeration and DMA smoke tests pass after each reset mode.
- Throughput remains above 94 Gbps per port for 30 minutes.
- Packet drop rate remains below 0.01 percent during line-rate traffic.
- Thermal stress test triggers warning and throttle events before shutdown.
- Debug logs preserve root cause evidence for firmware, DMA, PHY, and thermal failures.
