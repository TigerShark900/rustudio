# Team Create wire protocol

What rustudio's live Team Create client needs on the wire, decoded with
evidence. Companion to `TEAMCREATE.md` (which covers the REST/open flow). This
file is for the transport, the handshake crypto, the frame/reliability layer
and the replicator item formats.

Facts are tagged the same way as `TEAMCREATE.md`:

- **[verified: exe]** a string / RTTI / code in `RobloxStudioBeta.exe`.
  Addresses before §8 use the 0.744 copy (sha256
  `81be5bc2916ba979e0ecc68b5fd039a48821765c6e9a7bcfd8d27ad877cf1692`,
  `~/.local/share/rustudio/studio`). §8 uses the isolated 0.746 copy (sha256
  `7005e4f922fa44034884e84ad03fef943672c2b0b2eca46df5cc154331e46297`,
  `~/.cache/rustudio-dev/tc/studio`).
- **[verified: capture]** observed in a real or local-server packet capture.
- **[recalled, unverified]** public knowledge (gskartwii's roblox-dissector),
  not re-checked against this build.
- **[inferred]** follows from the above but not observed directly.

> Status 2026-11-05: **rustudio joins real Team Create servers directly,
> loads the live DataModel into its editor, and synchronizes primitive property
> edits, creation, deletion, and reparenting across accounts.** The authorized
> Place B test loaded 331,116 instances. Main-account Studio confirmed
> the bot's folder creation, probe rename, CFrame change and reparent; the bot
> received Studio's size change and parent change. See §9 for exact formats,
> evidence, implementation limits and the current test procedure.

## 1. Transport selection

The join script decides the transport. rustudio mirrors Studio's
`NetworkClient` "Transport selection" logic [verified: exe, TEAMCREATE.md §4]:

- **RbxTransport (QUIC)** when the join script has a `NetStackPort`, a
  non-empty `NetStackTokenValue` and the server's `ephemeralEarlyPubKey`.
  This is the Team Create / CloudEdit default
  (`FFlagUseRbxTransportClient3=True`,
  `FFlagEnableRbxTransportEphemeralEarlyPubKeyCloudEditClientLoading2=True`,
  `DFFlagRbxTransportSessionCrypto=True` in an offline Studio's flag snapshot)
  [verified: exe/flags].
- **RakNet** otherwise, to `MachineAddress:ServerPort`.

Implemented: `joinscript::JoinScript::transport_choice` and
`transport::DialPlan::from_join`.

### Local Studio test server (offline aid)

A Studio-hosted local server (Play Solo / "Server & Clients", and what a local test server
drives) starts an **RbxTransport QUIC server** and logs
`Started RbxTransport network server …|<port>` (port is random per start).
Its client join script carries [from a local test server, not yet
re-verified here]:

- `NetStackTokenValue: "bG9jYWxfdGVzdA=="` (base64 "local_test"),
- `NetStackPort: <that port>`, `MachineAddress`/`ServerPort`/`ServerConnections`,
- empty `TokenValue` and `ClientTicket`, `UdmuxEndpoints: []`,
  `DirectServerReturn: true`.

RakNet is avoided locally because its connection password differs between
engine versions. `joinscript::JoinScript::is_local_test` recognises this shape.
This local server is a cooperative offline target to iterate the QUIC framing
and replicator decode against before touching real Roblox.

## 2. Handshake crypto

### RakNet path (SessionCrypto)

Confirmed strings in the exe [verified: exe]:

- The offline connect uses Roblox's `RbxOpenRequest1` / `RbxOpenReply1` /
  `RbxOpenRequest2` / `RbxOpenReply2` in place of stock RakNet's
  OpenRequest1/2. Trace strings:
  `Received RbxOpenRequest1 from %s`, `Received RbxOpenRequest2 from %s`.
- `RbxOpenRequest1` carries a protocol byte; a mismatch logs
  `RbxOpenRequest1 Incompatible Protocol` and `RbxOpenRequest1 has incorrect size %d`.
- `RbxOpenRequest2` is a **sealed box encrypted to the server's early public
  key**. Error strings around the builder/parser (all [verified: exe],
  referenced near the builder at ~`0x1436706d1`):
  - `RbxOpenRequest2 no session crypto`
  - `RbxOpenRequest2 no public key`
  - `RbxOpenRequest2 using encryption {}`  ← logs the chosen encryption id
  - `RbxOpenRequest2 desired encryption is unset`
  - `RbxOpenRequest2 key exchange version incorrect for connecting to %s server`
  - `RbxOpenRequest2 unexpected aad size %d`
  - `RbxOpenRequest2 declared box size %d exceeds received size`
  - `RbxOpenRequest2 mac was previously used but did not create active rss`
  - `RbxOpenRequest2 failed to encrypt` / `decrypt failed for %s`
  - `RakNetValidateRbxOpenRequest2BoxSize` (a named validator).
- Server early public key distribution [verified: exe]:
  - a client-settings key ring
    `{"creationTime":"11:59 4/1/2024","applications":{"RakNetEarlyPublicKey":{"versions":[{"id":5,"value":"%s","allowed":true}],"send":5,"revert":5}}}`
    — note **key version id 5** is current for `RakNetEarlyPublicKey`.
  - the per-session key is `RbxTransportEphemeralEarlyPublicKey` (join reply
    `ephemeralEarlyPubKey`), with its own key ring template (version id 1).
- After the handshake every datagram is AEAD-encrypted;
  `ID_NEW_INCOMING_CONNECTION: SessionCrypto not found` drops a connection
  that never established crypto.
- RTTI classes present: `SessionCrypto@Security@RBX`,
  `QuicSessionCrypto@Security@RBX` [verified: exe].
- Primitives: the bundled OpenSSL provides X25519 and ChaCha20-Poly1305 /
  AES-GCM; there is no libsodium string. Which SessionCrypto uses, the box
  format, the key-exchange version number, and which side selects the
  encryption are **[unknown]** — to be read from a capture + the decompiled
  `RbxOpenRequest2` builder.

### RbxTransport path (QUIC) — captured 2026-11-04 [verified: capture]

A real join to **Place B [DEV]** (universe 8947175370, place
71871420864106) from our own online Studio 0.746 as testuser1, captured in
the rig's netns (`~/.cache/rustudio-dev/tc/cap/tc_placebdev_join.pcap`). Studio
chose RbxTransport (`selectedTransport=RbxTransport`,
`canUseRbxTransport=true`); RakNet was not used. What the capture shows:

- **Server/relay endpoint `128.116.63.33:54991`** (the join payload's
  `MachineAddress` was an internal `10.26.5.150:51943`; the public relay is
  the connected address). 18k frames / 25 MB arrived from it in ~2 s — the
  initial DataModel stream.
- **QUIC v1, TLS 1.3**, `ALPN = "rbx-rtcio"`, offered cipher suites
  `0x1302` (AES-256-GCM) and `0x1303` (ChaCha20-Poly1305), key share on the
  standard groups. So it is ordinary IETF QUIC underneath, once the relay
  header is removed.
- **A relay (RUPP/UDMUX-style) header wraps every datagram**, before the
  QUIC packet:

  ```
  [u8 version=1][u8 flags=0][u16 big-endian header_len][ header bytes ][ QUIC packet … ]
  ```

  `header_len` was **31** client→server and **23** server→client.
  `tools/tc/rig/strip_rupp.py` strips this header and rewrites the datagrams
  as plain IPv4/UDP, after which tshark dissects them as QUIC
  (`-d udp.port==<p>,quic`): Initial, then Handshake, then 1-RTT, with
  `rbx-rtcio` in the ClientHello.

  **Header layout, correlated with the QUIC CIDs** (Place B [DEV] capture,
  `rupp_parse.py`) [verified: capture]:
  - After the 4-byte prefix comes `01 11`, then one or more TLV-ish fields.
  - The id in the header is a **RUPP routing token, not the QUIC connection
    id** — it is 15–16 bytes and does not equal the 20-byte QUIC DCID/SCID.
  - The **first** client→server datagram uses an initial 16-byte token
    (`01 <16B>`); once the session is established, both directions switch to a
    negotiated **15-byte** token (`02 08 <15B>`) that is the same in both
    directions (the relay's connection key).
  - Client→server datagrams carry an **extra trailer TLV** `02 06 <6B>` that
    server→client lacks — likely the DSR / client endpoint hint
    (`DirectServerReturn` was true, `RuppConfig … DSR …` in the exe).
  - So: `[01][00][u16 hlen] 01 11 <token-TLV> [02 06 <6B> (C→S only)]`.
  - Open: the exact TLV type/length grammar and how the token derives from the
    join script's `TokenValue`. Constructing a valid header for a *new*
    connection needs the exe's RUPP builder (`RuppConfig`, `RuppTokenLog`
    strings) plus the per-session `TokenValue`; it is not reconstructable from
    the capture structure alone. This is the gating unknown for the Path-A
    client (below).
- Studio's own log: `RbxTransportDummyClient` starts a **1000 ms ping thread**
  and a **5000 ms time-sync thread** right after `Handshake complete`.

#### QUIC key recovery from process memory [verified: capture]

Since `SSLKEYLOGFILE` doesn't cover QUIC (below), the keys come from the
Studio process memory. `tools/tc/rig/quic_keys.py`, run as root-in-userns
(`tcstudio runroot`, which has `CAP_SYS_PTRACE` over the Studio we started):

1. reads the QUIC **ClientHello random** from the capture (tshark decrypts the
   Initial with the DCID, so the random and `rbx-rtcio` ALPN are in clear);
2. scans `/proc/<pid>/mem` for that 32-byte random (it sits in OpenSSL's `SSL`
   object), and trial-derives a TLS 1.3 traffic secret from each nearby
   window (RFC 9001 §5.1: HKDF-Expand-Label `quic key`/`quic iv`/`quic hp`);
3. **accepts a secret only if it removes header protection and AEAD-opens a
   real 1-RTT packet** of that direction — so a hit is self-verifying.

Result on the Place B [DEV] join (cipher **`0x1302`**, TLS_AES_256_GCM_SHA384, so
48-byte secrets): the **client application traffic secret** was found at
**+1520 bytes from the client_random** (inside the `SSL` struct) and verified
by decrypting a client→server 1-RTT packet. The secret is written to an NSS
keylog (`CLIENT_TRAFFIC_SECRET_0 …`) in a 0600 folder, used only by the local
tshark, then shredded. No key value is printed.

The **server** application traffic secret (which protects the server→client
DataModel stream) could **not** be recovered this way: an exhaustive
trial-decrypt scan of every high-entropy 48-byte window in the process's
writable memory (regions < 256 MB) matched **none** of the server→client
1-RTT packets. Conclusion [verified: capture]: the client keeps its own tx
secret resident (found at client_random+1520), but the **rx (server) secret
is not retained as plain bytes** — ngtcp2/OpenSSL installs the rx key/iv/hp and
discards the secret (there is no rx key-update need the client must serve). So
the next step for the server direction is **not** another secret scan but one
of:
  - scan for the derived **rx key (32 B) + iv (12 B) + hp (32 B)**, which
    ngtcp2 stores together (`ngtcp2_crypto_aead_ctx`/`ngtcp2_crypto_km`);
    validate by AEAD-opening a server packet, guessing the small packet
    number to avoid needing hp first, or finding hp in the same struct;
  - or hook the exe's `ngtcp2_crypto_ossl` `set_encryption_secrets` path to
    log both secrets as they are installed (an LD_PRELOAD can't reach the
    statically-linked code, so this means a small in-memory patch or a
    breakpoint via the Studio we start).

The **client** direction is fully decrypted and decoded (below), which already
covers what rustudio must *send* for Phase 2 edits.

#### Decrypted framing on `rbx-rtcio` [verified: capture]

With the recovered client secret, `tools/tc/rig/quic_decode.py` decrypts the
client→server 1-RTT packets (tshark mis-tracks CIDs on the stripped pcap, so
this is our own RFC 9001 decryptor). What rides on the QUIC connection:

- **Reliable data = QUIC STREAMs, unreliable = QUIC DATAGRAM frames.** The
  client opens many **client-initiated unidirectional streams** (ids 2, 6,
  10, 14, 42, 46, 50, 54 …) and also sends `DATAGRAM` frames, plus `PING`/`ACK`.
- **Each stream begins with an RbxTransport channel header**
  `06 01 04 <u32 counter> …`, where the `<u32 counter>` increments per stream
  (0, 1, 2, …). So `rbx-rtcio` multiplexes its channels onto QUIC streams and
  tags each with a type/sequence; the replicator items are the stream bodies.
- Exact field meaning of the `06 01 04` header and the item layout inside the
  stream bodies is the next decode, and needs the server→client direction (the
  initial DataModel) — i.e. the server secret.

This is the proof that the capture + memory-key pipeline decrypts real
RbxTransport traffic. The client→server direction is exactly what rustudio
must *produce* for Phase 2 edits, so it is directly useful even before the
server secret lands.

#### Server direction: installed key material from memory (path B, done) [verified: capture]

Path B worked on a fresh join (`tc_placebdev_join3.pcap`, Place B [DEV], server
relay `128.116.63.33`, both CIDs 20 bytes). `tools/tc/rig/quic_rxkm.py`, run
as rig root (`tcstudio runroot`) against the joined Studio (the process that
owns the UDP socket, found with `tcstudio runroot ss -unp`):

1. **Scan for AES-256 encryption key schedules.** ngtcp2's OpenSSL backend
   keeps each direction's AEAD key and header-protection key as
   `EVP_CIPHER_CTX`s, i.e. as expanded AES key schedules, and the first 32
   bytes of an AES-256 schedule are the raw key. A numpy test of the first
   expanded word, then a full 240-byte re-expansion, over every writable
   region found **30 distinct AES-256 keys** in ~45 s (both byte orders are
   tried; the hits were the plain AES-NI layout).
2. **Header-protection key**: the candidate that unmasks the first 40 1-RTT
   packets of a direction to reserved-bits-zero headers with consecutive
   packet numbers. Exactly one per direction.
3. **AEAD key and IV without scanning for the IV**: for each remaining key K,
   GCM's tag gives `E_K(J0) = tag XOR GHASH_H(aad, ct)` with `H = E_K(0)`, so
   `J0 = D_K(...)`; the right key yields `J0 = nonce || 00000001`, and the
   static IV is `nonce XOR pn`. The IV must come from a packet with a 2+ byte
   packet number (see below), otherwise IV bits 8–15 come out wrong.
4. Accepted only if (key, iv, hp) AEAD-opens the following packets.

Result: one (key, iv, hp) per direction; the server key schedule and the
client key schedule sat ~9 KB apart on the heap, the two HP schedules 0x1c0
apart [verified: capture]. Written as `DIR key iv hp` lines to a 0600 file
under `~/.cache/rustudio-dev/tc/keys`, used by `quic_decode.py --km`, shredded
afterwards. **Every 1-RTT packet of the join decrypts: server 25834/25834,
client 10116/10116**, no key update during the ~2 min session.

Why the earlier secret scan missed it: the client *secret* is resident (it is
also kept for key updates), the server one isn't; the derived key/hp are.

**RbxTransport packet numbers don't start at 0** [verified: capture]: the
first server 1-RTT packet was pn `0x90f9`, the first client one
`0x70fc2d45`. A decoder that assumes small pns gets the IV high bits wrong;
`quic_decode.py` reconstructs pns per RFC 9000 A.3 and brute-forces the high
part only for the first packet.

`quic_decode.py OUT --km KEYFILE server OUTDIR` reassembles every STREAM
(no holes) and writes `stream_<id>.bin` + `datagrams.bin` (decrypted place
data: keep under `~/.cache/rustudio-dev/tc`, never in the repo).

#### Path A (be the client) — QUIC up live [verified: live 2026-11-05]

rustudio's own process now joins a live session's QUIC. `transport::connect_quic`
is a quinn client with ALPN `rbx-rtcio`, cipher `0x1302` preferred, the RCC
certificate pinned by the join script's `certHashes`, over `rupp::RuppSocket`
(a `quinn::AsyncUdpSocket` that adds/strips the RUPP header). Verified against
Place B [DEV]: the TLS 1.3 QUIC handshake completes, ALPN negotiates, RTT ~15 ms.

**The RUPP token grammar, resolved from a live join** [verified: capture + live]:

```
[u8 version=1][u8 flags=0][u16 BE total header length] TLV*
TLV = [u8 type][u8 length][value]
  type 1 (TokenTlv), length 17: [u8 token-type][16-byte token]
  type 2 (Ipv4Tlv),  length 6:  [4-byte IPv4][u16 BE port]     (client->relay only)
```

- The client's **first** datagrams use `TokenTlv` token-type **1** carrying
  the 16 bytes of `base64-decode(NetStackTokenValue)` (not `TokenValue`; that
  is the RakNet token), plus an `Ipv4Tlv` naming the RCC
  (`MachineAddress:NetStackPort`). They are sent to the UDMUX address
  (`UdmuxEndpoints[0].Address`) on `NetStackPort` — i.e. the client dials the
  relay, not the internal RCC address. This matches Studio's log
  `UDMUX Address = <relay>, Port = <NetStackPort> | RCC Server Address = <rcc>`.
- Every **relay->client** datagram carries `TokenTlv` token-type **2** with a
  16-byte token the relay rotates ~once a second
  ("Switching to new TT token received from RCC"); the client echoes the most
  recent one on its subsequent datagrams. `RuppSocket` tracks and echoes it.
- `header_len` is 31 client->server (with the Ipv4Tlv), 23 server->client.

**Dialing: the server QUIC endpoint is self-signed; the cert is pinned by
`NetStackConfig.certHashes`** (base64 SHA-256 of the server cert DER). The
join reply's `settings.NetStackConfig` is URL-encoded JSON
`{pubKey (32B X25519), port, caps (12B), certHashes[]}`; `pubKey != EphemeralEarlyPubKey`.
`transport::PinnedCert` accepts exactly those hashes and checks the TLS 1.3
handshake signature with `rustls::crypto::verify_tls13_signature`.

**The matchmaker reply shape** [verified: live]: `POST gamejoin /v1/team-create`
returns `{status, message, settings, joinTicket}` — the join script is under
**`settings`** (PascalCase), not `joinScript`. gamejoin answers a browser user
agent with `HTTP 500 InternalServerError`; it needs a Studio user agent
(`RobloxStudio/WinInet`) and the `robloxctx-authenticated-userid` header.
`matchmaker::Matchmaker::join` runs GetCanCollaborate → team-create-preemptive
→ `/v1/team-create` and returns the parsed `JoinScript` + the raw reply (a
secret).

#### The RbxTransportSessionCrypto hello — the remaining wall [verified: live]

With the QUIC transport up, rustudio opens the lanes in Studio's order
(channel 4 lanes 0,1,2,4,7–13; the `ctrl` streams on channels 0/4/6; channel
6 lane 1 for ping) and sends the opening replication messages built from the
join script: `0x90` (protocol/flag sync + the player JSON, compact, Studio's
key order — see `handshake::player_json`), `0x92` (place verification),
`0x8a` (submit ticket: zigzag user id, `ClientTicket`, a per-build middle,
the `SessionId` JSON), `0x8f 00`. **The server accepts all of this**: it opens
its own control and ping lanes (channel 4/0/6 `ctrl`, channel 6 lane 1) and
**echoes our 1 Hz ping**, so the framing, the lane model and the opening
messages are correct on the wire.

**But the server never sends the DataModel.** The replication lane proper is
gated on two messages rustudio does *not* yet fully produce, the
`RbxTransportSessionCrypto` hello [RTTI `QuicSessionCrypto@Security@RBX`,
`RbxTransportSessionCrypto` flag, both verified: exe]:

- `0xa8` — in the reference capture, 103 bytes: `a8 11 21 <33B> 42 <66B>`.
  §8 now pins its producer: Studio Base64-decodes fields 3/4 of the current
  `ClientTicket` and parses its last field as the suite. These are
  server-supplied per-session bodies, **not a fresh client X25519 key**.
- `0xa7` — 2259 bytes in that capture: `a7 <u16le block_count> <ciphertext>`.
  Its count is 141 and 3 + 141×16 = 2259. Serializer `0x1461de980` writes
  exactly this 16-byte-block form; the plaintext and key schedule are still
  being recovered.

Replaying a stale capture's `0xa8` verbatim changes nothing because its ticket
bodies are session-bound. The `0xa8` can instead be generated afresh from each
join's `ClientTicket` (`sessioncrypto::Hello::from_client_ticket`); an offline
known-answer test reproduces the captured packet **byte for byte**. The
separate `EphemeralEarlyPubKey` join field URL-decodes to Base64 and then 32
bytes; it is not the five-field input to the `0xa8` builder.

The `0xa7` is **not a second crypto handshake**: its caller is Studio's
SharedStringCache producer `0x1461ded00`. It announces 16-byte cache hashes;
a new client can encode an empty list with `shared_string_cache_message`.
The `0x92` is also per-session: `place_verification` implements Studio's fresh
random-u32/build-mask/ZigZag construction, with a captured known-answer test.

Live status after these fixes: rustudio opens the replication lanes and gets
`0x93`, but the server immediately resets lane 1 with application error
`0x10000000106` (Roblox error 262, generic data/reconnect). No DataModel yet.
The remaining failure is therefore in the opening/session negotiation, not an
unimplemented `0xa7` cipher.

#### The SSLKEYLOGFILE gap [verified: capture]

**`SSLKEYLOGFILE` does not capture the QUIC/ngtcp2 TLS secrets.** Studio
honours the env var for its HTTPS/WebView stack — the login capture logged 41
TLS 1.3 + 2 TLS 1.2 sessions, and those decrypt — but the **QUIC ClientHello
random from the Team Create handshake is absent from the key log** (checked
every `tls.handshake.type==1` on the stripped flow; zero keylog hits). So
Studio's `ngtcp2_crypto_ossl` QUIC path never wires
`SSL_CTX_set_keylog_callback`, and the replicator stream stays encrypted.
HTTPS is decryptable with the keylog; the QUIC replicator is not.

**This is the concrete wall reached this session.** The frames, the transport
choice, the relay framing and the QUIC/TLS/ALPN parameters are decoded from
real traffic; the encrypted QUIC payload (CRYPTO frames, then the replicator
items) is not. The only way through, since the env keylog doesn't cover QUIC,
is to **read the QUIC TLS secrets from the Wine process memory**
(`/proc/<pid>/mem` of the Studio we start; its ngtcp2/OpenSSL `SSL`/`SSL_SESSION`
holds the client/server handshake and application traffic secrets). Dump
them, write an NSS-format keylog, and tshark decrypts the stripped QUIC. That
memory-dump work is the next step.

The keylog from this capture was **shredded** after its labels were counted;
the pcap is kept (its QUIC is encrypted and needs the above secrets, and its
HTTPS is now unreadable without the shredded keylog).

### RbxTransport path (QUIC) — from the binary

[verified: exe]

- QUIC via **ngtcp2** with OpenSSL TLS
  (`ngtcp2_crypto_ossl_configure_client_session`). PQ key share
  `X25519MlKem768` is available; WebTransport is optional
  (`DebugRbxTransportClientUseWt`).
- Channels: reliable streams + unreliable datagrams, fragmented/reassembled by
  `RbxTransportChannelTracker`, plus ping and time-sync channels.
- Dials the RCC address and `NetStackPort` directly, or through UDMUX with a
  RUPP token: `RuppConfig = RCC {}:{}, DSR {}, Token type {}` and
  `Client will connect to server {}|{}, udmux {}|{}`.
- `RbxTransportSessionCrypto` wraps a Roblox crypto layer on top of TLS.
- Exact channel framing and the SessionCrypto-over-TLS layer are **[unknown]**.

## 3. Replicator items

Vocabulary confirmed from RTTI (`…Item@Replicator`) [verified: exe,
TEAMCREATE.md §4]: `NewObjectItem`, `DeleteInstanceItem`,
`DestroyInstanceItem`, `ChangePropertyItem`, `ChangeAttributeItem`,
`EventInvocationItem`, `MarkerItem`, `PingItem`, `TagItem`, `JoinDataItem(V2)`,
`ClusterItem`, `SharedStringItem`, `StreamDataItem`, `InstanceIntentItem`,
`ResolveNewInstanceAtomicTreeItem`, `SharedReferencePropertyChangedItem`,
`StatsItem`.

Top-level packet ids and `ID_DATA` sub-items from gskartwii
[recalled, unverified] are recorded in `replicator::packet_id` and
`replicator::ItemKind`; the capture below supersedes them where they differ.

The initial place arrives as the JoinData stream (`tcinitialstreambytes`,
`DMInitialStream`): shared strings then instances, compressed [verified: exe].

### 3b. Decoded server→client stream (Place B [DEV] join, Studio 0.746) [verified: capture]

Everything below is from `tc_placebdev_join3.pcap`, decrypted with the
recovered key material (§2) and decoded by `tools/tc/rig/rtcio_split.py`,
`rtcio_schema.py`, `rtcio_instances.py` and `rtcio_items.py`. Hex excerpts
are structural only (ids, lengths, generic names); no tokens or keys appear
in this stream.

**QUIC streams.** All data rides on unidirectional streams (server-initiated
ids 3, 7, 11, … and client-initiated 2, 6, 10, …), plus DATAGRAM frames.

- Each stream starts `06 01 <u8 channel> <4 bytes>`: the 4 bytes are a
  big-endian sequence number, or ASCII `ctrl` on control streams
  (`06 01 04 63 74 72 6c`).
- Then messages, each `<u32 BE: 0x80000000 | length> <length bytes>`. Every
  stream of the join splits exactly on this framing (no leftovers).
- Channel 4, sequence 1 is **the replication stream** (server stream 23:
  24 730 messages, 24.2 MB; client stream 6: 4528 messages).
- Channel 6, sequence 1 carries 274 77-byte messages, byte-identical in both
  directions (an echo: ping/time-sync) [inferred].
- Channels 0/4/6 also have small `ctrl` streams (`02`/`00`-tagged messages
  of 2–10 bytes) and empty channel-4 streams with sequences 0, 2, 4, 7–13
  (opened per reliability lane, unused in this session) [inferred].
- DATAGRAM frames carry a 3–4 byte header (`07 41 da 00`, `02 41 db 00`)
  then ordinary `83 05/06 …` ping items.

**Messages on the replication stream**, by first byte (= the classic Roblox
packet id):

| id | count | what |
|---|---|---|
| `0x93` | 1 | protocol/flag sync: `93 00 <u16 LE n>` then n × (`<u16 LE len> key`, `<u16 LE len> value`): `AnimGraphServerAuthorityPhaseSyncSkip`=`true`, … (51 pairs) |
| `0x97` | 1 | the schema, below |
| `0x81` | 1 | the top-level service table: `81 01 …` then entries `<u32 LE id> <u16 LE class> 01 01 01` (e.g. id `0x6580` → class `0x12d` Lighting) |
| `0x84` | 1 | `84 01 00 00 00` |
| `0x83` | 6532 | ID_DATA: a list of items, ended by `00` |
| `0xa5` | 18194 | Net asset transfers (union geometry), decoded 2026-11-05: begin `a5 02 fe 04 <ref> 00 <varint compressed len>` (ref = `u32 1, u8 1, u16 0, u8 tag, varint id`, as in the SolidMeshHolder property), chunks `a5 01 fe <u16 LE index> <≤512 B>`, end `a5 03 fe <varint>`; `a5 06 01 <varint>` carries no data. Joined chunks = varint decompressed size + an LZ4 block = the SolidMeshHolder blob without its `03 01` prefix. All 2645 transfers of the Place B [DEV] join decode; 5371 unions resolve (`replicator::net_asset_msg`, `model` NetAsset) |

**The schema (0x97).** `97 <u32 LE compressed len> <u32 LE size> <zstd>`.
Decompressed (354 837 bytes): a 9-byte prefix (`03 01` + 7 zero bytes),
then:

- `varint nEnums`, and per enum `varstr name, u8 bits`: 610 enums;
- `varint nClasses, varint totalProps, varint totalEvents`: 638 / 12259 /
  7026;
- per class `varstr name`, `varint nProps`, then per prop
  `varstr name, u8 type` plus extra bytes (type `0x07` enum: `u16 LE` enum
  index; type `0x3c`: 1 byte). After the props come `ff ff`, then
  `varint nEvents` and per event `varstr name, varint nArgs`, with
  `nArgs × (u8 type, u16 LE enum or ffff)`;
- `varint n` content-URL prefixes (26: `rbxassetid://`, …);
- `varint n` common instance names (127: `AccessoryWeld`, `Animate`, …).

Classes are listed alphabetically, and each class lists its inherited props
after its own (e.g. `Accessory` ends with `Archivable … UniqueId,
numExpectedDirectChildren`). Varints are unsigned LEB128. **Class index**,
**class-local prop index**, **global prop index** and **global event index**
(running counts in this order) are what the items reference.

**ID_DATA (0x83) items** (`rtcio_items.py`; server: 6526/6532 messages
decode completely, client: 4513/4522):

| item | layout | seen |
|---|---|---|
| `16` initial-stream chunk | `<u8 stage> <u32 LE clen> <u32 LE size> <zstd>`, then `<u32 LE> <u8>` unless stage 1 | 1627: stage 1 ×1216, 2 ×65, 3 ×2, 4 ×344 |
| `0d` instance batch | `<u32 LE records> <u32 LE clen> <u32 LE size> <zstd> <u8 04>`; the payload is exactly `records` instance records, then shared-string entries (script sources, `CSGPHS` blobs) | 11, after the join; batch roots have a nil parent |
| `02` new instance | `<ref> <u16 LE class> ff {<u8 prop> <value>}* ff <parent ref>` | inside `10` |
| `03` property change | `<ref> <u16 LE global prop> <u8 v> <value>` (v = 1 from the server, 0 from the client) | server 2, client 8467 |
| `07` event | `<ref> <u16 LE global event> <args typed by the schema>` | 7 / 16 |
| `10` batch | `<u32 LE n>` + n items | 1 (the joining player) |
| `13` reparent | `<child ref> <new parent ref>` | 2581; every one of the 2454 nil-parent roots of the `0d` batches is reparented by one (to Folders/Models) |
| `23` | `<u32 LE>` | 3834 (`83 23 00 00 00 00 00` keep-alive-like) |
| `05` / `06` | ping / ping-back, opaque, alone in their message | ~500 each |

A **ref** is `01 <u32 LE id>`, or `00` for nil. Ids are server-assigned
(DataModel = 13, Workspace = 14 here).

**Instance records** (the `16` stage 2–4 streams and the `0d` batches):

```
01 <u32 LE id> <u16 LE class> { <u8 prop index> <value> }* ff  <parent ref>
```

Only non-default props are sent; for example a Name equal to the class
default is omitted. Excerpt (a LocalScript, redacted):

```
01 86 65 00 00   32 01   00 <16B source hash>  07 26 "{…GUID…}"
0e 09 "BootCover"  13 <16B UniqueId>  ff  01 d5 23 00 00
```

The prop indices here are Source (`00`), ScriptGuid (`07`), Name (`0e`) and
UniqueId (`13`), and the parent is id `0x23d5`.

- Stage 1 is the shared-string table: `{16B hash, u8 0, varint len, bytes}*`.
  It holds script sources and other blobs, referenced by hash.
- Stages 2, 3 and 4 are each one continuous record stream, and records cross
  chunk boundaries, so the chunks must be concatenated before parsing.
- Result: **6349 shared strings and 329 045 instances**. Every stage stream
  and all 11 `0d` batches parse completely (a batch's trailing shared strings
  include `<roblox!` binary-model blobs).
- Counts include 252k `Part`, 16.6k `MeshPart`, 9.4k `WeldConstraint` and
  7.4k `Model`. The 67 services hang off id 13.

**Property value encodings** (schema type id → wire form):

| type | wire | example props |
|---|---|---|
| `02` string | varint len + UTF-8 | ScriptGuid, TimeOfDay, AttributesReplicate (attribute blob as a string) |
| `06` ProtectedString | 16-byte shared-string hash | Script.Source |
| `07` enum | varint | Material (`a0 06` = 800), Technology |
| `08` BinaryString | varint len + bytes | SerializedOverrides, ChildData |
| `09` bool | u8 | Anchored |
| `0a` int32 | zigzag varint | numExpectedDirectChildren, TriangleCount |
| `0b` float | f32 LE | Transparency |
| `0c` double | f64 LE | TimePosition |
| `0d` UDim | f32 scale, i32 offset | UICorner radii |
| `0e` UDim2 | f32, i32, f32, i32 (X.Scale, X.Offset, Y.Scale, Y.Offset: order inferred, samples were symmetric) | Frame.Position/Size |
| `12` BrickColor | u16 LE | RopeConstraint.Color |
| `13` Color3 | 3 × f32 | Lighting.Ambient |
| `14` Color3uint8 | 3 bytes | BasePart.Color3uint8 |
| `15` Vector2 | 2 × f32 | AnchorPoint |
| `16` Vector3 | 3 × f32 | size, InitialSize |
| `19` Vector3int16 | 3 × i16 | TerrainRegion.ExtentsMin/Max |
| `1a` CFrame | 3 × f32 position, then u8 rotation id; id 0 → 9 × f32 matrix follows | CFrame, PivotOffset |
| `1c` Instance | ref (`01 <u32>` / `00`) | PrimaryPart, Part0/1 |
| `21` Content (old) | varint len + string | LinkedSource, HSRAssetId |
| `22` SystemAddress | varint (`02` seen) | NetworkOwnerV3 |
| `23` NumberSequence | u32 LE n + n × (time, value, envelope) f32 | Transparency |
| `25` NumberRange | 2 × f32 | Lifetime |
| `26` ColorSequence | u32 LE n + n × (time, r, g, b, envelope) f32 | Beam.Color |
| `29` PhysicalProperties | u8 flags (0 = default); bit0: 5 × f32, bit1: +1 f32 (acoustic) | CustomPhysicalProperties |
| `2c` int64 | zigzag varint | SourceAssetId, UserId |
| `2e` SharedString | 16-byte hash | Tags, MeshData2, PhysicalConfigData |
| `31` Name | u8 b: `b & 0x80` → common-name dictionary entry `b & 0x7f`, else b = length of a string that follows | Name |
| `32` OptionalCFrame | u8: 0 = none, else `0x80 \| rotation id` (0 → 9 f32), then 3 × f32 position | WorldPivotData |
| `34` UniqueId | 16 bytes | UniqueId, HistoryId |
| `36` Font | u16 LE weight, u8 style, u32 LE len + family, u32 LE len + cached face id | FontFace |
| `37` SecurityCapabilities | u64 LE | Capabilities |
| `3c` SolidMeshHolder | u32 LE n + n × (u8 1, u16 0, varint id, u32 LE 3, u32 LE 0) | Union/IntersectOperation |
| `3d` Content (new) | u8 kind: 0 = none, 1 = varint len + URI | MeshContent, AudioContent |

Not seen yet, so not decoded: `0f` Ray, `10` Faces, `11` Axes, `1d` Tuple,
`1e` Array, `1f` Dictionary, `28` Rect, `30` DateTime, `39` ReplicationPV,
`3a`, `41`–`45`. The 6 server messages that fail stop on `1d`/`1e`/`1f`
(event args) or on `44` (Player.User).

**Collaborator presence** [verified: capture]:

- The joining editor gets an `83 10` batch. It holds `02` new-instance items
  for the editor's Player, Backpack and **`Collaborator`** (class 141; props
  `CollaboratorColor3` (Color3), `UserId` (int64), `Username` (string)).
- Then come the events `CollaboratorsService.CollaboratorInstanceCreatedSignal(UserId)`
  and `LiveScriptingService.BroadcastMessage("<user> joined live editing
  session.", 0)`.
- The presence state then changes through ordinary `03` items, for example
  `03 01 96 38 05 00 e7 09 01 01`: Collaborator id `0x053896`, global prop
  `0x09e7` = `Collaborator.Status`, v1, value enum 1.
- Collaborator `CFrame` / `CurDocGUID` updates weren't exercised in this
  session (the rig's camera never moved). They use the same `03` item with
  the Collaborator class props (`CFrame` = prop 0, type `1a`).
- More examples: `03 01 0e 00 00 00 28 2f 01 20 <32 ASCII hex>` sets
  `Workspace.WatermarkHash`. The client sends `03` items for ref fix-ups
  (`Model.PrimaryPart`, `Weld.Part1`, `Sound.SoundGroup`, …; v0), and
  events such as `LiveScriptingService.LiveEditingClientConfiguration('{"version":"0.746.0.7461264"}')`.

Not yet mapped to user actions: create/change/delete made by a *second*
editor (the optional Argon-driven step). The item forms they will use
(`02`, `03`, and a delete item not seen in this capture) are the ones above.

## 3a. Live session facts (read-only Luau probe)

One read-only probe, run 2026-11-04 through the user's Argon plugin in their
live **Place B** Team Create Studio (session `halloween-castle`, a
bridge where nothing syncs). It made no edits and didn't move the camera.

- **A Team Create editor is a CloudEdit *client* of the RCC:**
  `RunService:IsEdit()=true`, `IsClient()=true`, `IsServer()=false`
  [verified: live]. That fits "every collaborator is a client on the RCC"
  (TEAMCREATE.md §5). rustudio joins as a client, not a server.
- **Presence isn't reachable through `GetService` at plugin/command
  security:** `game:GetService("CollaboratorsService")` returned `nil`
  [verified: live]. The `Collaborator` fields listed in api-dump.json
  (`UserId, Username, CFrame, CollaboratorColor3, CurDocGUID, IsIdle, Status`)
  are probably held engine-side or replicated without being exposed to Luau
  that way [inferred]. Their wire form has to come from a capture. Do
  **not** plan to read presence through plugin Luau.

## 4. Capture plan (to produce [verified: capture] facts)

Goal: a real a live Place A session / Place B Team Create join from our own
online Studio (testuser1), captured and decrypted, plus the matching local
Studio-server capture for comparison.

1. **Own online Studio**, isolated from the host's own Studio: a separate Wine
   prefix + HOME, or a copy of the offline Studio
   Studio install with real networking instead of the mock. Sign in with
   Studio's "Login via Browser" (never inject the cookie into Studio's creds —
   0.744 discards it). The browser half uses a dedicated Chromium profile
   seeded from the keyring cookie over CDP (pattern:
   `~/.cache/rustudio-dev/main/login.sh`).
2. **Packets without root**: run that Studio in an unprivileged netns
   (`unshare -Urn` + pasta/slirp4netns for connectivity); inside it we hold
   CAP_NET_RAW, so tcpdump works without sudo.
3. **Keys**: QUIC/TLS key logging (`SSLKEYLOGFILE` if its OpenSSL honours it),
   else read keys from the Wine process memory via `/proc/<pid>/mem` for the
   process we started. RakNet SessionCrypto keys the same way.
4. **HTTPS** (gamejoin team-create, GetCanCollaborate, join script): a local
   proxy with our own CA trusted only in that prefix.
5. Decode handshake → framing → replicator, filling §2 and §3.

### Blockers (found 2026-11-04, both cleared the same day)

- ~~`quinn` not vendored offline~~ **Cleared.** `quinn 0.11` + `rustls 0.23`
  (ring provider) + `tokio` were fetched online once and are now in the cargo
  cache, so the crate builds `--offline` again.
  `transport::quic_client_endpoint()` builds a QUIC client endpoint, and a
  test checks that it binds (no network traffic).
- ~~No capture tooling~~ **Cleared.** `tcpdump`, `tshark` and `pasta` are
  now installed. `unshare -Urn sh -c 'tcpdump -D'` lists interfaces, so
  capturing inside an unprivileged netns works without sudo, and pasta gives
  that netns connectivity.
- REA/Ghidra has the binary analyzed (cache hit) but `resolve_containing_procedure`
  on the handshake address times out at 330 s on this 217 MB PE; decompiling
  the `RbxOpenRequest2` builder will need a narrower request or a longer budget.

### The capture rig (`tools/tc/rig/`), built 2026-11-04

`tcstudio` runs **our own online Studio 0.746.0.7461264** (a copy of the
own Studio version dir; the user's install and prefix are untouched) as
testuser1. The layers, outermost first:

1. **Headless gamescope (1600x900).** It has its own display and input, so
   nothing appears on or grabs the user's desktop.
   - `tcstudio shot F` uses `gamescopectl screenshot`, which also captures
     GPU and WebView2 content. An X grab shows those areas as black.
   - `tcstudio click X Y` clicks through xdotool. XTEST clicks do reach Wine
     here; `key` presses didn't land on the Qt dialog.
2. **`pasta --config-net --no-pidns -4 -i wlan0 -T none -U none --no-map-gw`.**
   A user and network namespace with internet. Its root shell stays alive
   (`rootpid`), because that's where `tcpdump` runs (`tcstudio cap NAME`).
   `enp9s0`'s default route is dead from pasta; `wlan0` works.

   > **SAFETY (fixed 2026-11-04, after it happened).** Without `-T none -U
   > none --no-map-gw`, pasta forwarded the namespace's loopback and gateway
   > to the host, and the rig Studio's **Argon plugin auto-connected to the
   > USER's Argon on `127.0.0.1:8000` and `:8005`** (their live Place B and
   > Place A Team Create sessions). An Argon connection to 8005 could sync a
   > different place into the user's repo and live session. Two defences now:
   > (a) the pasta flags above — verified from inside the netns that
   > `curl 127.0.0.1:8000` and `:8005` fail while `www.roblox.com` works;
   > (b) every local-server plugin is moved out of the rig prefix to
   > `~/.cache/rustudio-dev/tc/disabled-plugins/` (`Argon.rbxm`, and the offline Studio
   > copy's `PlaceB_ImageUploader/MeshUploader/Weathering.lua`). After any `up`,
   > re-verify (a) before opening a place.
3. **A nested `unshare --user --map-user=<uid>`** where Wine runs as the
   real uid, with a private D-Bus and `HOME` under `~/.cache/rustudio-dev/tc`.
   `tcstudio run CMD` enters it with nsenter.

The prefix is a copy of the offline Studio's (it has WebView2), with three changes:
- `strip_creds.py` removes the offline Studio's fake saved logins.
- `fix_prefix.py` repoints Local AppData (and `LOCALAPPDATA`) to
  `~/.cache/rustudio-dev/tc/appdata` and drops every `HKCU\Software\Roblox` key.
- The `Documents` and `Pictures` symlinks to the user's real folders are
  replaced with empty folders.

Gotchas found getting Studio to start, each one verified:
- **A bare Studio window on gamescope fails with `CreateWindowEx failed`.**
  Run it in a Wine virtual desktop instead: `explorer /desktop=tcstudio,1600x900`.
- **Wine's explorer segfaults in glibc (a NULL argument) during display
  setup under a minimal `env -i`.** Fixed by passing `SHELL`, `TERM`,
  `XDG_SESSION_TYPE`, `XDG_CURRENT_DESKTOP`, `XDG_DATA_DIRS`,
  `XDG_CONFIG_DIRS` and `XCURSOR_SIZE`, plus gamescope's own variables and
  the real `XDG_RUNTIME_DIR`. The symptom is
  "no driver could be loaded"; `maps_catch.py` traced the fault to libc.
- **The capture Chromium runs `--headless=new`.** A windowed one takes
  gamescope's only visible slot. `xdg-open` hands it https URLs over CDP
  `Target.createTarget`. `/json/new?URL` cuts the URL at its first `&`, which
  produced "RouterParamMissingOrInvalid: client_id".

How Studio signs in (verified, 0.746):
- **The first login page is a WebView2 page** with a username and password
  form and "Another Logged In Device". It's
  `www.roblox.com/login?returnUrl=apis.roblox.com/oauth/v1/authorize?client_id=7968549422692352298&response_type=code&redirect_uri=roblox-studio-auth:/…`.
  It has no browser button.
- **When the embedded flow fails, Studio offers "Login via Browser"**, then
  "Retry Browser Login". These open
  `authorize.roblox.com/?client_id=7968549422692352298&response_type=code&redirect_uri=roblox-studio-auth:/…`
  through `xdg-open`. Signed in, that page shows "Select Account to
  Continue to Roblox Studio" (testuser1), then Continue.
- `cdp.mjs … authorize` clicks through, catches the `roblox-studio-auth:`
  redirect over CDP and hands it to the rig's `xdg-open`, which passes it to
  Studio. The redirect is never printed.

**Studio honours `SSLKEYLOGFILE` for its HTTPS stack** [verified:
2026-11-04], but **not for QUIC** (see §2, the decryption wall). The login
capture logged 41 TLS 1.3 + 2 TLS 1.2 sessions and those HTTPS flows decrypt;
the QUIC Team Create handshake's secrets never reach the keylog. The log is a
secret: written to a 0700 folder, used only for decryption, then shredded.

**Sign-in is fully automated now** (the ToS was accepted for testuser1 by the
account holder on 2026-11-04). The sequence that logged in and captured a
join:
`tcstudio up` → `tcstudio chromium` + `setcookie` (headless, signs testuser1)
→ `tcstudio studio` with `TC_EXTRA_ENV="SSLKEYLOGFILE=…/keys/sslkeys.log
WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9555"` → when
the embedded WebView2 login shows, `cdp.mjs 9555 follow roblox.com/login`
(navigates it to the OAuth authorize URL; it then fails over to the browser
button) → click "Login via Browser"/"Retry Browser Login" (`tcstudio click
775 500` / `767 500`) → `cdp.mjs 9444 catchauth` (a browser-wide watcher that
catches the `roblox-studio-auth:` redirect from
`apis.roblox.com/oauth/v1/authorizations` and hands it to the rig's
`xdg-open`; the redirect is never printed) and `cdp.mjs 9444 authorize
client_id=` (clicks Continue). Studio logs `login [end][success]`,
`Authenticated : YES`. Then `tcstudio cap NAME` and
`tcstudio run xdg-open 'roblox-studio:1+launchmode:edit+task:EditPlace+placeId:<p>+universeId:<u>'`.

## 5. Crate map (`crates/rustudio-net`)

| Module | What | State |
|---|---|---|
| `joinscript` | Parse `JoinInformation` (Pascal/camel), transport choice, local-test detection | done + tests |
| `matchmaker` | `/v1/team-create` + `GetCanCollaborate` bodies, `GameJoinResponse`, polling | done (join gated by `LiveJoinConsent`, never auto-run) + tests |
| `transport` | `DialPlan`; `QuicTarget::from_join`; `PinnedCert` (certHashes); `connect_quic` (quinn + RUPP, ALPN `rbx-rtcio`, cipher 0x1302) | **QUIC up live** + tests; `connect()` seam kept |
| `rupp` | `RuppSocket`: a `quinn::AsyncUdpSocket` wrapping the relay header, echoing the relay's rotating token | done + test (header shape matches capture); verified live |
| `rtcio` | channel framing: `open_lane`/`send`/`read_header`/`read_msg`, DATAGRAM lanes, the 77-byte ping | done + test; verified live (server echoes pings) |
| `handshake` | build the client's `0x90`/`0x92`/`0x8a`/`0x8f` opening messages + `player_json`, using a decrypted capture as a per-build template | done; accepted by the live server |
| `replicator` | `split_stream` (rtcio framing), `Schema` (0x97), `Decoder::decode_frame` (0x83 items 02/03/07/10/13/16/0d/23/pings, instance records, ~30 value types) → `RepOp`s | done + tests; on the real Place B [DEV] stream: 330k ops, 6 undecoded messages (value types 1d/1e/1f/44) |
| `model` | `LiveModel`: builds a `WeakDom` from `RepOp`s, resolves out-of-order parents, binds the DataModel referent via Workspace's parent, applies `Reparent` | done + tests; `examples/tc_view.rs` renders a recorded session |
| `lib::open_team_create` | starts the explicit live-session join through `LiveSession::connect` | done |
| examples | `tc_join` (matchmaker → describe join shape), `tc_connect` (join → QUIC up), `tc_probe` (join → open lanes + send opening + print the server's answer) | research aids; print structure only, no secrets |

Secrets: tokens/tickets/keys are `Redacted` (Debug/Display = `<redacted>`).
The join reply is a secret too; `tc_join`/`gj.py` write it only to a 0600
file under `~/.cache/rustudio-dev/tc/keys` for inspection — shred it after.

## 6. Handoff (2026-11-04, end of session)

- **Readable:** both directions of `tc_placebdev_join3.pcap`. To redo on a new
  join: `tcstudio up` → `tcstudio studio` (saved token reused) →
  `tcstudio cap NAME` → `tcstudio run xdg-open 'roblox-studio:1+launchmode:edit+task:EditPlace+placeId:<p>+universeId:<u>'`
  → wait for the place → `tcstudio runroot ss -unp` (Studio pid, relay
  port) → `strip_rupp.py` → `tcstudio runroot python3 -I quic_rxkm.py PID
  STRIPPED CLIENT_IP ~/.cache/rustudio-dev/tc/keys/km.txt` (Studio must still be
  joined) → `quic_decode.py STRIPPED SRC_IP 20 --km km.txt server OUTDIR` →
  `rtcio_instances.py OUTDIR` / `rtcio_items.py OUTDIR` / `cargo run -p
  rustudio-net --example tc_view -- OUTDIR/stream_23.bin`. Shred the key
  file when done.
- **Exact next step:** capture a session where a second editor (the user's
  Studio via Argon exec, Workspace folder `rustudio_tc_test` only) creates,
  edits and deletes instances and moves the camera while the rig is joined
  to the *same* place, to pin the delete item, the Collaborator `CFrame`
  update and the `02`/`03` forms of user edits; then decode the remaining
  value types (`1d` Tuple, `1e` Array, `1f` Dictionary, `44`). This session
  the user's port-8000 Studio was in a different place (log: place
  100000000000004, not Place B [DEV]) and the Argon tagged-print channel in the
  Studio logs was stale (logs last written ~30 min earlier), so the step
  was skipped; join the rig to the user's place or watch effects in the
  capture instead.

## 7. Handoff (2026-11-05, live-join session)

**What now works live** (rustudio's own process, host network, never the
user's Argon ports — checked `ss -tnp :8000/:8005` shows only the user's
Studio):

1. `matchmaker::Matchmaker::join` → a real join script for Place B [DEV], live and
   Place B [🎃] (Studio UA + `robloxctx` header; the join script is under
   `settings`).
2. `transport::connect_quic` → the live session's QUIC is up: UDMUX relay +
   RUPP token (type 1 join → type 2 relay, echoed), ALPN `rbx-rtcio`, cipher
   0x1302, cert pinned by `certHashes`. (`cargo run --release -p rustudio-net
   --example tc_connect -- 8947175370 71871420864106`.)
3. `rtcio` + `handshake` → the client opens Studio's lanes and sends
   `0x90/0x92/0x8a/0x8f`; the server opens its control/ping lanes and echoes
   the 1 Hz ping. (`--example tc_probe -- <u> <p> <template-stream> <secs>`;
   artifacts in `checks/tc/`.)

**The wall:** the DataModel does not stream until rustudio sends a valid
`RbxTransportSessionCrypto` hello (`0xa8` 103 B + `0xa7` ~2.2 KB), generated
per session from the server's `EphemeralEarlyPubKey` (X25519) and a fresh
client key. Stale captured hellos are ignored. Phases 1–5 (live view,
presence, two-way edits) all sit behind this one handshake.

**Exact next step:** compare the current Studio `0x8a` and rustudio's `0x8a`
at the serializer, then isolate the server's immediate error-262 reset after
`0x93`. The fresh `0xa8`, shared-string-cache `0xa7`, and fresh `0x92` are
implemented and have known-answer tests. `QuicSessionCrypto` (0.746 copy:
vtable `0x149690b58`, ctor `0x146223ab0`, ref `0x146223b51`) is a key-holder
lead for encrypted datagrams, not an explanation for the SharedStringCache
packet. Once lane 1 survives, feed it into `replicator::Decoder` +
`model::LiveModel` for the live view. Presence (the `Collaborator` `03`
items, §3b) and edits (`02`/`03`/delete) then ride the same decoded stream in
reverse. A fresh join script to inspect: `tc_join <u> <p>
~/.cache/rustudio-dev/tc/keys/join.json` (0600; shred it).

## 8. Handoff (2026-11-05, SessionCrypto session)

### Static: the `0xa8` builder is located [verified: exe]

`0x14609e5a0` (body ends `0x14609e858`) serializes the client SessionCrypto
hello. It is called from `0x1460975a8` (function `0x1460970f0`). It does not
run crypto itself: it reads three fields from its object (`rdi`) and appends
them to a byte buffer:

| field | type | wire |
|---|---|---|
| `+0x10f0` | `std::string` (data, size at `+0x1100`, cap at `+0x1108`) | `u8` size, then the bytes |
| `+0x1110` | `std::string` (data, size at `+0x1120`) | `u8` size, then the bytes |
| `+0x1130` | `u8` | one byte |
| `+0x1138` | `u8` | gate: hello is only built when non-zero |

The first byte is the packet id `0xa8`. A live capture from Studio 0.746 has
exactly this shape:

```
a8 11 21 <33 bytes> 42 <66 bytes>           = 103 bytes
```

so the first field is 33 bytes, the second 66 bytes, and `+0x1130` is `0x11`.
The two lengths are the low bytes of the corresponding `std::string` sizes,
not separate version fields. The 33-byte field starts with a 32-byte
high-entropy key-looking value; the 66-byte field is high entropy. The
per-session variation in both captures is confined to the two field bodies.

The caller chain is reached from the join-settings parser
`0x1460b0b30`: it reads **`ClientTicket`** (the actual field-name bytes at
`0x149672de0`; an earlier handoff misread them as `EphemeralEarlyPubKey`) and
calls `0x1460a06f0`. That function stores the value at `+0x230`, splits it
(`0x1438f72f0`, separator `;`), requires at least five pieces, allocates the
hello holder (`0x14608d250`), Base64-decodes fields 3/4 through
`0x1408082b0`, and parses the last field as a decimal suite byte. A live join
response has exactly this five-field ticket shape. The separate
`EphemeralEarlyPubKey` response field has no semicolons and Base64-decodes to
32 bytes.

`sessioncrypto::Hello::from_client_ticket` implements this path. The decoded
body lengths can vary by ticket: the reference capture is 33/66 bytes, while
a later live ticket decoded to 32/64, so `WIRE_LEN` describes the reference
shape rather than a protocol invariant.

### Static: QuicSessionCrypto construction [verified: exe]

- `0x146223ab0` is the inner constructor; it allocates a 0x98-byte base object
  and installs vtable `0x149690b58`.
- `0x146223cb0` is the public wrapper. It copies one 32-byte value from
  `rdx` into inner `+0x40..+0x5f` and one from `r8` into `+0x60..+0x7f`
  (two 16-byte copies each), then sets `+0x28 = r9b`, `+0x2a = 1`,
  `+0x2d = 1`.
- It is called from `0x146091cca` and `0x1461416fa` (client/server QUIC
  setup). In the second caller the two source blocks are stack `+0x210` and
  `+0x230`.
- A joined Studio has exactly one object with vtable `0x149690b58`; its
  `+0x40` and `+0x60` are two high-entropy 32-byte values. Public work on
  Roblox's RakNet `RakPeerCrypto` places the tx key at `+0x40` and rx key at
  `+0x60`; whether QuicSessionCrypto reuses those offsets is still
  [inferred], but the object shape matches.

### Static: class and key-holder facts [verified: exe]

The vtable at `0x149690b58` is the `QuicSessionCrypto` object vtable and
`0x1491485c8` is the base `SessionCrypto` vtable (`0x1436a0890` is its
constructor). `QuicSessionCrypto` is `SessionCrypto` plus two 32-byte keys at
`+0x40` and `+0x60`; the factory `0x146223cb0` takes them from two contiguous
blocks produced by a virtual call at the transport's `[vtable+0xc0]`
(`0x146091c9b`, consumer `0x146091cca`). The call also fills a status/cipher
byte at the third 32-byte slot. It is therefore likely TLS-exported or
early-key material, not itself the `0xa8` key exchange [inferred].

The base object (0x40 bytes) has vptr `0x1491485c8`, an SSO string
`"UniqueNumber"` at `+0x10`, and state flags at `+0x28` (have key), `+0x29`
(keys derived), `+0x2a` (peer key), `+0x2b` (failed), `+0x2c`
(AES-GCM/ChaCha), `+0x2d` (established).

### Static: candidate RakNet KDF core [verified: exe; no QUIC link shown]

`0x14368a720` accepts four 32-byte inputs and stores them at SessionCrypto
state `+0x40/+0x60/+0x80/+0xa0` (four keys). `0x14368a850` takes a 32-byte
input from its caller and calls `0x147a44840` twice, deriving 32-byte pairs
into `+0xc0/+0xe0` and `+0x100/+0x120`. `0x147a44840` is a BLAKE2b-based
keyed derivation: it calls the bundled BLAKE2b init-key (`0x147a490a0`),
update (`0x147a49090`) and final (`0x147a49070`) routines, producing 64
bytes and splitting them into two 32-byte halves. Type names near the
primitive are `HashStateBlake2b@Crypto@RBX` / `HashStateBlake3`.

This is a **RakNet-side** candidate, not an established QUIC KDF: its state
writes through `+0x120`, whereas the QuicSessionCrypto allocation is only
0x98 bytes. No shown call graph connects the two. The input ordering, key vs
message roles and any QUIC-specific labels remain unknown.

The negotiated RakNet AEAD is AES-GCM or ChaCha20-Poly1305 with a 12-byte
nonce and 16-byte tag. The sealed message layout is
`AAD header | ciphertext | nonce[12] | tag[16]` — 28 trailer bytes; the
seal/open pair is `0x1436a0dc0` / `0x1436a0cd0`, and `0x1436895a0` parses the
wire form. A nonce counter lives at crypto `+0x8` and field names
`txNonce`/`rxNonce`/`rakIsAesGcm` exist in the binary. Reuse by QUIC is
unproven, especially because the captured `0xa7` has a 16-byte-block shape.

### Rejected lead: a client private key in `0xa8`

A post-join memory scan found no aligned raw X25519 private scalar whose
public key occurred in the captured `0xa8`. The earlier handoff concluded that
the scalar must have been freed. That conclusion was invalid: the scan tested
the wrong producer model. Static parsing and the live join shape show that
both `0xa8` bodies come from `ClientTicket`, so this message does not require
a client private key at all. The separate 32-byte `EphemeralEarlyPubKey` may
still participate in the remaining key agreement, but its consumer must be
traced independently.

The two 32-byte values retained at QuicSessionCrypto `+0x40/+0x60` are only
high-entropy candidates until a known-message decryption or a verified
key-install path identifies them; calling them “final keys” is premature.

### Status

- The QUIC transport, lanes, `0x90/0x92/0x8a/0x8f` and ping are already live.
- `0xa8` is fully framed and generated from `ClientTicket` by
  `sessioncrypto::Hello::from_client_ticket`; `tc_probe ... a8` sends that
  fresh form before the opening messages.
- `0xa7` (2259 bytes) is located at serializer `0x1461de980`: its little-
  endian count is 141 and its payload is 141 sixteen-byte SharedStringCache
  hashes. A breakpoint took the call through `0x14609ed9a` to producer
  `0x1461ded00`, whose own strings are `shared-string` and
  `ExperienceStringMap-*`. It is not ciphertext. The earlier AEAD trials were
  therefore testing the wrong packet model.
- `0x92` is a fresh nonce, not a constant: `place_verification` implements
  `(random_u32 << 32) | (random_u32 ^ 0x9d58f351)`, ZigZag-varint encoded,
  and reproduces the reference `92 98 81 dd 95 b3 c7 a9 83 08` exactly.
- Live with fresh `0xa8`/`0x92` and a valid cache announcement, the server
  opens the lanes and sends `0x93`, then resets lane 1 with
  `0x10000000106` before any acknowledgment can be sent. No live DataModel
  yet, so `Editor::open_team_create` remains gated.
- No signature check was found in the `0xa8` serializer. That scoped negative
  does not rule out attestation inside a ticket body or the `0xa7` plaintext.

### Disconnect 0x106: display mapping and limits (2026-11-05)

Offline inspection of Studio SHA-256
`7005e4f922fa44034884e84ad03fef943672c2b0b2eca46df5cc154331e46297`
establishes its disconnect-message switch at `0x145fef0c0`. It subtracts
`0x102` from the input code and indexes the RVA table at `0x145fef4f0`.
For `0x106`, the entry selects `0x145fef1a1`, which loads a 42-byte string
at `0x149662220`: `Error while sending data, please reconnect`.
Protocol mismatch is `0x103`; unsupported version is `0x102`; ticket
processing failure is `0x109`. Reproduce with standard-library-only
`python3 tools/tc/rig/disconnect_codes.py PATH_TO_STUDIO_EXE`;
`checks/tc/disconnect_codes.txt` records the output. The script verifies the
binary hash and instruction bytes before interpreting the table.

This is a display mapping, **not an identified root cause**. Validated
instruction decoding also finds `mov edx, 0x106` in the join-processing
functions `0x1460cc250` and `0x1460ce270`. The former invokes the disconnect
helper `0x14601f250` at `0x1460cd307` after constructing a `Player Creation
Error` reason, and at `0x1460cd87f` in the branch containing
`UnsupportedLuauVersion`. The latter has corresponding sites
`0x1460cf10d` and `0x1460cf661`. Streaming-state failures also use this code.
Thus the code alone does not establish authentication success/failure,
SessionCrypto failure, a transport send failure, or a Luau-version mismatch.
The remote server's actual generating branch remains unknown.

The saved `tc_probe_control_handshake.txt` still shows the same reset after
sending the captured channel-4/channel-6 control messages. Their addition
has not established a fix. Do not treat those opaque messages as verified
capability negotiation. Next useful evidence is the join parser's accepted
fields and Luau-version check, compared with the generated opening packets.

These observations come from local PE parsing and objdump/Capstone decoding;
they are not REA runtime observations or evidence of the remote server's code.

## 9. Direct live client and cross-account verification (2026-11-05)

`rustudio-net::live::LiveSession` now performs the matchmaker join, QUIC/TLS,
opening handshake, heartbeats, schema decode and ongoing replication on a
cancellable worker. `--team-create UNIVERSE PLACE` opens it in the editor;
Open from Roblox uses the same path for Team Create places. The editor's
separate journal reader sends local edits and advances past remote changes
without echoing them or putting them into local undo history.

The authenticated join requires the Studio 0.746 transport capability
extension `ff00`, with little-endian mask `000dd3e750f30892`. The optional
rustls patch is documented in `vendor/rustls/RUSTUDIO-PATCH.md`; ordinary
HTTPS clients omit the extension. Matchmaker SessionId JSON must preserve
BrowserTrackerId=0. The protocol-sync tail is a build constant, not a JSON
checksum. Embedded opening templates contain flags/build constants only.

### Additional verified formats

- References are `<unsigned-varint peer scope> <u32 LE index>`; scope zero
  means nil and has no index. Existing server objects commonly use scope 1;
  peer-created objects retain another scope. Internally these use a u64
  `(scope << 32) | index` (scope 1 keeps the legacy low-u32 representation).
- SET_GLOBALS assigns the client's creation namespace after seven boolean
  flags, as an unsigned varint. The second flag enables an optional terrain
  block; creation currently rejects that configuration instead of guessing.
  Native client parser: `1460466f3`, `146046c24`, `146046f74..146047047`.
- DeleteInstanceItem is item `01`, followed by the instance reference.
- Client property changes use item `03`, reference, global u16 LE property
  index, version byte **0**, and the typed value. Server-origin versions in
  the observed edits are 1.
- **Parent is a reserved reference descriptor at `global_props.len()`**,
  outside every class's ordinary property list. The observed schema has
  12,259 ordinary properties, so Parent is `e3 2f`. Its value is a reference.
  This is the correct client reparent format. Item `13` is the server's
  ResolveNewInstanceAtomicTreeItem; it must not be sent as a normal reparent.
  Resending NewObject can reset omitted properties, so it is unsuitable as
  a parent-only update.
- StreamDataItem `0d` starts with a u32 record count. **Zero count omits the
  compression header and payload.** Nonempty batches contain clen, size,
  zstd records and shared strings. Both end in region markers: a flags byte,
  low bits 0 means a full region coordinate follows, 1..3 are relative region
  deltas, 4 is the sentinel; bit 3 means another marker follows. A coordinate
  is mode 0 plus three i8 or mode 1 plus three i32 LE values. Native serializers
  `14618d4e0`, `14618d7a0`, `1465ab2a0`.
- JoinDataItemV2 non-shared-string stages end with a u32 and a varint count
  of pairs, each two varints. The formerly assumed fixed five-byte trailer
  only describes an empty metadata table.
- Camera updates originate on the client's Player property
  `CloudEditCameraCoordinateFrame`, not on the server-owned Collaborator.
  The editor sends changed camera frames at most every 200 ms and renders
  collaborator markers from incoming Collaborator instances.

### Cross-account test

The user explicitly connected their main Place B Studio to an
Argon bridge on port 8000. The bridge project had no file mappings and kept
unknown instances. All edits were confined to Workspace.rustudio_tc_test.
The bot account joined the same server, independently of Studio's account.
Two sessions using the same bot account are not a valid peer test: Roblox
kicks the earlier editor with error 0x114.

`examples/tc_live_peer.rs` is an opt-in live probe requiring that test folder.
It creates `rustudio_outgoing_probe` inside it, then receives a marked Part
created through Studio, renames it to `rustudio_sync_probe_ack`, changes its
CFrame to (12345,12345,12345), and reparents it under the new folder. Studio
confirmed the name, parent, CFrame, Size=(1,1,1), Anchored=true and original
attribute. Studio then changed Size to (2,3,4); the bot received that update.
A Studio parent change also decodes through the reserved descriptor. Deleting
an outgoing test folder was confirmed absent in Studio. Evidence summaries
are in `checks/tc/live_cross_account*.txt` and
`checks/tc/cross_account_verified.txt`. Raw streams stay outside the repository
in mode-600 cache files, including the optional RUSTUDIO_TC_STREAM_OUT and
RUSTUDIO_TC_BAD_FRAME diagnostics.

### Limits

The live editor supports objects and explicit script draft commits. Simultaneous
Jupiter OT remains separate work (the a5 geometry channel is decoded: see the message table).
Unsupported outgoing property types produce an editor error and block live
saving, so an incomplete local edit cannot be reported as saved. Forward
instance references resolve when their targets arrive. Ready still uses schema
+ marker + instances + 1.5 seconds of quiet as a heuristic, not a protocol
completion acknowledgment. Templates and the TLS mask target Studio 0.746.

## 10. Script drafts, atomic commits, saves and presence (2026-11-05)

### Protected Source and shared strings

The shared-string identity is BLAKE2b-128. A protected Source property contains
the 16-byte identity, followed by the inline record: repeated identity, byte
encoding zero, varint byte length and UTF-8 source. NewObject places protected
properties in its early group and writes shared records after both property
groups. Source property changes consume their inline records before decoding
the next item. Typed event arrays/dictionaries are preserved by the decoder. Arbitrary bytes
in string-typed values are retained without lossy UTF-8 conversion.
AttributesReplicate maps to editable Attributes using rbx_types serialization;
attribute writes use the inverse mapping. A regression test covers marker,
Unicode bytes and floating-point attribute values.

A marked ModuleScript under Workspace.rustudio_tc_test was used for real
cross-account tests. rustudio changed its Source; Studio observed it. Studio
changed it again; rustudio decoded the incoming source. The ModuleScript was
never required or executed. Sanitized evidence: checks/tc/live_script_source.txt.

### Native atomic replacement

LiveScriptingService first receives LiveEditingClientConfiguration with the
string JSON `{"version":"1"}`. SendAtomicOperation arguments are int32 request
ID, ScriptGuid string, operation JSON string and lowercase **MD5** of the base
source. This MD5 is distinct from the shared-string BLAKE2b hash. Replacement
uses this operation shape (positions zero, omit empty contents atoms):

```json
{"payload":{"atoms":[{"type":1,"position":0,"contents":"old source"},{"type":0,"position":0,"contents":"new source"}]},"timestamps":{"local":0,"remote":0}}
```

SendAtomicUpdateResponse returns request ID and status: 0 success, 1 missing
GUID, 2 base hash mismatch, 3 illegal operation. Real tests passed for no-op,
insertion and complete replacement. Reusing the old base after replacement
returned status 2, and Studio confirmed that the rejected text did not apply.
Evidence: checks/tc/live_script_atomic.txt and live_script_atomic_unicode.txt
(the latter additionally verified a Unicode replacement in Studio); implementation: src/scripts.rs in
rustudio-net. This is explicit atomic draft replacement, not Jupiter OT.

The editor stores private drafts in
`$XDG_STATE_HOME/rustudio/script-drafts/<place>/<ScriptGuid>.json` (fallback
`~/.local/state`), with mode-700 directories and mode-600 atomically replaced
files. Incoming peer edits update the server baseline while retaining local
drafts. Conflicts expose server/draft comparison and explicit replacement.
Acknowledgments apply to the submitted text snapshot, preserving newer typing.
A timeout or rejection retains the draft. Saving waits for drafts to be
committed or discarded. Where no atomic service/GUID exists, Source fallback
retains a recovery copy until server confirmation. Clean focused buffers follow
incoming server Source updates.

### Collaborative save and publish

TeamCreatePublishService.TeamCreatePlaceUploadRequest takes a typed dictionary:
`publish` bool and `upload_to_edge` bool (false). The response contains success
and metadata, including `version_number`. The native handler was inspected and
encoding/decoding is tested against the negotiated event schema. The editor
routes live Save/Publish here, without requiring an Open Cloud API key. It marks
only the requested revision saved after success; timeout warns to check Version
History before retrying. Error status enum 0 is PlaceTooLarge, 1 approaching
limit, 2 upload failing, 3 no error. Unsupported document writes block later
save requests in both the editor and ordered network worker. **No real save or
publication was triggered against the user's game during these tests.**

### Presence

Player.CloudEditSelectionChanged carries an array of instance references.
CloudEditPlayerActive tracks activity, with a five-minute idle threshold.
Changed selection/camera updates are throttled to 200 ms. The collaborator
window lists users and idle state and offers fly-to and available peer script
locations. Incoming selection outlines and camera markers draw only inside the
3D viewport. Outgoing script document/line presence is not yet sent. A real cross-account
selection test passed: Studio selected the marked script, rustudio received
its reference array, then Studio's previous selection was restored. Evidence:
checks/tc/live_selection_presence.txt. Marked test objects and the empty test
folder were removed after verification.

Studio Team Chat was removed January 30, 2025; the historical chat checklist is
obsolete. Primary source: [Roblox Creator Roadmap, spring 2025 update](https://devforum.roblox.com/t/creator-roadmap-2025-spring-update/3624895).

### CSG transfer verification (Studio 0.746, 2026-11-06)

The a5 implementation predates this pass; the recorded Place B join still decodes
all **2,645 transfers / 5,371 resolved UnionOperation holders**, with zero
replicator errors after enforcing sequential chunk indices and exact transfer
lengths. Each transfer is serialized on this lane; indices restart at zero.
Malformed/truncated transfers now produce diagnostics and cannot install partial
geometry. Compressed and expanded blobs have a local 64 MiB resource limit
(this is not an inferred Roblox protocol maximum). A later holder property
supersedes a pending older reference, so a late old transfer cannot overwrite it.

**Native reader evidence.** Re-decompiled the offline executable (SHA-256
`81be5bc2916ba979e0ecc68b5fd039a48821765c6e9a7bcfd8d27ad877cf1692`):

- `0x1429808f0` takes the MSVC string storage and calls `0x14297fc60`.
- `0x14297fc60` checks the nine-byte `SolidMesh` signature via `0x142980eb0`,
  requires version zero at byte 9, consumes 13 bytes, reads positions, normals,
  UVs and colours, then four corner-index arrays via `0x14298c740`.
- `0x14298c740` is the signed 7/23-bit delta-index reader described in
  STUDIO-SKY-RE.md, "Unions". `0x142980930` computes the serialized size from
  the four vertex arrays and four encoded index arrays; it is a size routine,
  not the byte-writing serializer. The a5 sender/byte-writer entry points
  have not been identified in this pass.
- Direct consumers of the string wrapper include `0x14364c380` and
  `0x144038320`; these corroborate that the payload is solved render geometry.
  This is static evidence, not a trace of a live Studio executing those calls.

**Mapping to the file DOM.** a5 transfers resolve the references in wire type
`3c` **SolidMeshHolder**, stored in `.rbxl` as `NetAssetRef`. After LZ4 decoding,
prepend `03 01`; the captured minimal holder is then
`03 01 <u32 365> <u32 0> <u32 365> SolidMesh <u32 0> ...`.
The existing file renderer consumes exactly these bytes; geometry arrival marks
SolidMeshHolder dirty in cloud_ui so the same mesh path rebuilds the live union.
This applies to PartOperation-derived geometry; the recorded known answer is a
UnionOperation, not an independent Negate/Intersect capture.

The other union properties are separate stores, not alternate names for the a5
payload: **PhysicalConfigData** is a shared-string physics blob (`CSGPHS`),
**MeshData2 / MeshData** hold older solved `CSGMDL` render meshes (reader
`0x1428a05d0`, version-5 body `0x1428a1970`), **ChildData2 / ChildData** retain
CSG operands for reconstruction, and **AssetId** is an asset locator. Keep them
as replicated; do not copy SolidMesh bytes into any of them. The legacy format
and missing-operand-solver limits remain those in STUDIO-SKY-RE.md. Their full
serializer layouts, and a5 kind 6's exact lifetime semantics, remain unresolved.

**Known answer.** `crates/rustudio-net/tests/fixtures/csg-solidmesh.rtcio` is
only a complete 273-byte begin/chunk/end transfer from the older recorded join:
geometry, reference and transfer metadata, with no credentials or instance
names. It expands to 379 bytes, BLAKE2b-128
`47b98fb04896c60867735c080666284a`. Tests assert the exact hash/header, reject
truncated/misordered chunks, verify asset-before/after-instance order, suppress
superseded references, and round-trip the resulting holder through `.rbxl`.

**Read-only live check.** Joined universe 10000000003 / place 100000000000004,
read the initial model and disconnected: 54,068 instances, 17,131 shared strings,
zero decode errors. This join contains no a5 transfers or UnionOperation
instances, so it cannot independently verify union rendering. Capture, logs and
snapshots stay in the private cache. No edits/save/publish requests were sent.

Snapshot export exposed DOM typing bugs beyond geometry: Tags must decode from
the wire's shared string into `Tags`; int32/int64 and float32/float64 widths must
survive decoding; modern Content URI properties must become `Content`, including
legacy MeshPart/HSR aliases; WorldPivotData is `OptionalCFrame`. These conversions
now let the full recorded Place B and fresh live models serialize successfully.
`tc_view` accepts `RUSTUDIO_SNAPSHOT_OUT=/private/path.rbxl` for offline export,
so another live join is unnecessary when repeating these checks.

The captured known answer also renders successfully after export (silent editor
screenshot in private cache). `tc_csg_fixture OUT.rbxl` reproduces that local
rendering fixture without a server or raw capture. NegateOperation now shares
the union mesh dispatch in scene.rs (one necessary change outside the net/UI
ownership boundary), retaining its existing translucent editor appearance.
Validation: 47 crate tests + 4 captured-transfer integration tests pass;
`cargo build --release` succeeds. Existing unrelated app warnings remain.
