# esp32-ota-rollout

The release side of over-the-air firmware updates: a manifest with an integrity check, a dual-slot device model with automatic rollback, and a staged rollout controller that halts when a release makes devices fail.

It models how an ESP32 with two OTA partitions behaves and how a fleet should be updated, using only the Python standard library so it runs anywhere.

```
build image --> manifest (version, size, SHA-256)
                    |
   rollout controller: 5% canary --health gate--> 25% --health gate--> 100%
                    |                                  \--> halt if failures > threshold
   device: download to inactive slot -> verify -> boot pending -> self-test -> commit | revert
```

## What is verified, and what is not

| Part | Status |
|---|---|
| Manifest build and SHA-256/size verification | Unit tested, including tamper detection |
| Dual-slot update, commit, automatic rollback, downgrade and corrupt-image rejection | Unit tested |
| Staged rollout: stable cohorts, nested stages, hold, advance, halt | Unit tested |
| Fleet simulation of a good and a bad release | Runs with no hardware (`python -m ota_rollout.simulate`) |
| **Signature verification (authenticity)** | **Not implemented.** Only integrity (SHA-256) is checked. A signature over the manifest, verified against a key on the device, is the next layer |
| Real ESP32 OTA (`esp_https_ota`, partition table, bootloader rollback) | **Not implemented or tested.** This repo is the release logic and a behavioural model, not firmware |
| Transport, device registry, health telemetry from real devices | Not implemented; the simulator reports success or failure directly |

## Run

```
python3 -m unittest discover -s tests -t . -v      # 13 tests, standard library only
python3 -m ota_rollout.simulate                    # good release: rolls out to the whole fleet
python3 -m ota_rollout.simulate --bad              # bad release: halts at the canary stage
```

Example (bad release): the 5% canary devices fail their self-test and revert on their own, the controller sees the failure rate and halts, and the rest of the fleet is never offered the update.

## Design decisions

- **Never touch the running slot.** The new image goes to the inactive slot, so a failed update always leaves a bootable device.
- **Commit only after a self-test.** A new image boots as pending and is marked valid only once it proves healthy.
- **Hash-based cohorts.** A device's bucket comes from a hash of its id, so cohorts are stable and each stage includes the previous one.
- **Gate every stage on health.** The controller holds until enough devices report, advances on a low failure rate and halts on a high one.
- **Reject downgrades and respect `min_version`.** Prevents rollback attacks and unsafe jumps between incompatible versions.

## Next steps

Sign manifests (for example Ed25519) and verify on the device, add a persisted device registry, feed real health telemetry into the gate, and pair this with firmware using the ESP-IDF rollback API.
