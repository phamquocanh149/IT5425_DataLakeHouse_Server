<h2>:mag: Vulnerabilities of <code>noname12346767/my-minio@sha256:ff3fdcaaf08a067191989010ad2862da14e0238973f6586750d740adb6d589bc</code></h2>

<details open="true"><summary>:package: Image Reference</strong> <code>noname12346767/my-minio@sha256:ff3fdcaaf08a067191989010ad2862da14e0238973f6586750d740adb6d589bc</code></summary>
<table>
<tr><td>digest</td><td><code>sha256:ff3fdcaaf08a067191989010ad2862da14e0238973f6586750d740adb6d589bc</code></td><tr><tr><td>vulnerabilities</td><td><img alt="critical: 16" src="https://img.shields.io/badge/critical-16-8b1924"/> <img alt="high: 67" src="https://img.shields.io/badge/high-67-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/medium-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/low-0-lightgrey"/> <!-- unspecified: 0 --></td></tr>
<tr><td>platform</td><td>linux/amd64</td></tr>
<tr><td>size</td><td>47 MB</td></tr>
<tr><td>packages</td><td>270</td></tr>
</table>
</details></table>
</details>

<table>
<tr><td valign="top">
<details><summary><img alt="critical: 7" src="https://img.shields.io/badge/C-7-8b1924"/> <img alt="high: 6" src="https://img.shields.io/badge/H-6-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>golang.org/x/crypto</strong> <code>0.37.0</code> (golang)</summary>

<small><code>pkg:golang/golang.org/x/crypto@0.37.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-46595?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 10.0: CVE--2026--46595" src="https://img.shields.io/badge/CVE--2026--46595-lightgrey?label=critical%2010.0&labelColor=8b1924"/></a> <i>Incorrect Implementation of Authentication Algorithm</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>10</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:L</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.556%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>47th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Previously, CVE-2024-45337 fixed an authorization bypass for misused ssh server configurations; if any other type of callback is passed other than public key, then the source-address validation would be skipped.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-42508?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 9.1: CVE--2026--42508" src="https://img.shields.io/badge/CVE--2026--42508-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Improper Certificate Validation</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>6.910%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>94th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Previously, a revoked 'SignatureKey' belonging to a CA was not correctly checked for revocation. Now, both the 'key' and 'key.SignatureKey' are checked for @<!-- -->revoked.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39834?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 9.1: CVE--2026--39834" src="https://img.shields.io/badge/CVE--2026--39834-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Integer Overflow or Wraparound</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.597%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>49th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When writing data larger than 4GB in a single Write call on an SSH channel, an integer overflow in the internal payload size calculation caused the write loop to spin indefinitely, sending empty packets without making progress. The size comparison now uses int64 to prevent truncation.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39833?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 9.1: CVE--2026--39833" src="https://img.shields.io/badge/CVE--2026--39833-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Missing Authorization</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.469%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>41st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The in-memory keyring returned by NewKeyring() silently accepted keys with the ConfirmBeforeUse constraint but never enforced it. The key would sign without any confirmation prompt, with no indication to the caller that the constraint was not in effect. NewKeyring() now returns an error when unsupported constraints are requested.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39832?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 9.1: CVE--2026--39832" src="https://img.shields.io/badge/CVE--2026--39832-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Improper Preservation of Permissions</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.683%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>53rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When adding a key to a remote agent constraint extensions such as restrict-destination-v00@<!-- -->openssh.com were not serialized in the request. Destination restrictions were silently stripped when forwarding keys, allowing unrestricted use of the key on the remote host. The client now serializes all constraint extensions. Additionally, the in-memory keyring returned by NewKeyring() now rejects keys with unsupported constraint extensions instead of silently ignoring them.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39831?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 9.1: CVE--2026--39831" src="https://img.shields.io/badge/CVE--2026--39831-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Missing Authorization</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.478%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>42nd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The Verify() method for FIDO/U2F security key types (sk-ecdsa-sha2-nistp256@<!-- -->openssh.com, sk-ssh-ed25519@<!-- -->openssh.com) did not check the User Presence flag. Signatures generated without physical touch were accepted, allowing unattended use of a hardware security key. To restore the previous behavior, return a "no-touch-required" extension in Permissions.Extensions from PublicKeyCallback.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39830?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="critical 9.1: CVE--2026--39830" src="https://img.shields.io/badge/CVE--2026--39830-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Improper Restriction of Operations within the Bounds of a Memory Buffer</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.683%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>53rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A malicious SSH peer could send unsolicited global request responses to fill an internal buffer, blocking the connection's read loop. The blocked goroutine could not be released by calling Close(), resulting in a resource leak per connection. Unsolicited global responses are now discarded.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78662?s=golang&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.56.0"><img alt="high : CVE--2026--78662" src="https://img.shields.io/badge/CVE--2026--78662-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.56.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.56.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.431%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>38th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Previously, a channel registered in the mux's chanList is not usable until it is established. A malicious peer was able flood the channel's incomingRequests, deadlocking the entire connection.

Now, we add an atomic established state, set when a channel becomes usable. Until such a time, handlePacket drops every packet other than the open confirmation/failure, without blocking and without tearing down the connection.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56855?s=golang&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.56.0"><img alt="high : CVE--2026--56855" src="https://img.shields.io/badge/CVE--2026--56855-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.56.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.56.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.500%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>43rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Previously, after a channel has been established, a malicious peer could send crafted messages that would deadlock the entire connection.

Now, we handle all RFC 4254 channel messages; global requests are handled explicitly. Then, treat all other messages as a protocol error and tear the connection down instead of buffering and blocking.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56854?s=golang&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.55.0"><img alt="high : CVE--2026--56854" src="https://img.shields.io/badge/CVE--2026--56854-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.55.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.55.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.437%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>39th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The source-address critical option in the Permissions returned by an authentication callback was only enforced for the PublicKeyCallback and VerifiedPublicKeyCallback paths, extending the fix for CVE-2026-46595. Permissions returned by the PasswordCallback, KeyboardInteractiveCallback, NoClientAuthCallback, and GSSAPIWithMICConfig.AllowLogin callbacks were not validated against the client's remote address, so a source-address restriction set by those callbacks was silently ignored. The check is now applied to the Permissions returned by any authentication callback.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-46597?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="high 7.5: CVE--2026--46597" src="https://img.shields.io/badge/CVE--2026--46597-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Incorrect Type Conversion or Cast</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.473%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>41st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

An incorrectly placed cast from bytes to int allowed for server-side panic in the AES-GCM packet decoder for well-crafted inputs.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39829?s=github&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.52.0"><img alt="high 7.5: CVE--2026--39829" src="https://img.shields.io/badge/CVE--2026--39829-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Improper Validation of Specified Quantity in Input</i>

<table>
<tr><td>Affected range</td><td><code><0.52.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.52.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.467%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>41st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The RSA and DSA public key parsers did not enforce size limits on key parameters. A crafted public key with an excessively large modulus or DSA parameter could cause several minutes of CPU consumption during signature verification. This could be triggered by unauthenticated clients during public key authentication. RSA moduli are now limited to 8192 bits, and DSA parameters are validated per FIPS 186-2.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2025-47913?s=golang&n=crypto&ns=golang.org%2Fx&t=golang&vr=%3C0.43.0"><img alt="high : CVE--2025--47913" src="https://img.shields.io/badge/CVE--2025--47913-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.43.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.43.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.668%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>52nd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

SSH clients receiving SSH_AGENT_SUCCESS when expecting a typed response will panic and cause early termination of the client process.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 3" src="https://img.shields.io/badge/C-3-8b1924"/> <img alt="high: 24" src="https://img.shields.io/badge/H-24-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>stdlib</strong> <code>1.24.13</code> (golang)</summary>

<small><code>pkg:golang/stdlib@1.24.13</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-56857?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="critical : CVE--2026--56857" src="https://img.shields.io/badge/CVE--2026--56857-lightgrey?label=critical%20&labelColor=8b1924"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.553%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>47th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

On Windows, when the target of Root.Mkdir or Root.MkdirAll is a junction pointing to an empty location, the operation can create a directory at the junction target even when that target is located outside the root. This only applies to operations where the last path component is a junction (path/to/junction, but not path/junction/target).

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39821?s=golang&n=stdlib&t=golang&vr=%3C1.25.13"><img alt="critical : CVE--2026--39821" src="https://img.shields.io/badge/CVE--2026--39821-lightgrey?label=critical%20&labelColor=8b1924"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.13</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.13</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.834%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>79th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The ToASCII and ToUnicode functions incorrectly accept Punycode-encoded labels that decode to an ASCII-only label. For example, ToUnicode("xn--example-.com") incorrectly returns the name "example.com" rather than an error.

This behavior can lead to privilege escalation in programs using the idna package. For example, a program which performs privilege checks on the ASCII hostname may reject "example.com" but permit "xn--example-.com". If that program subsequently converts the ASCII hostname to Unicode, it will inadvertently permits access to the Unicode name "example.com".

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78663?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="critical : CVE--2026--78663" src="https://img.shields.io/badge/CVE--2026--78663-lightgrey?label=critical%20&labelColor=8b1924"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.858%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>59th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The HTTP/2 server can refund connection-level flow control twice for the same data: Once when a client resets a stream (refunding data for any sent-but-unread portion of the stream), and again when a request handler reads the buffered data. A malicious client can exploit this to bypass the configured connection-level flow control limit (MaxReceiveBufferPerConnection). Total buffered data is still limited by the concurrent stream limit and stream-level flow control.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39822?s=golang&n=stdlib&t=golang&vr=%3C1.25.12"><img alt="high : CVE--2026--39822" src="https://img.shields.io/badge/CVE--2026--39822-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.12</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.12</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.232%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>14th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

On Unix systems, opening a file in an os.Root improperly follows symlinks to locations outside of the Root when the final path component of the a path is a symbolic link and the path ends in /.

For example, 'root.Open("symlink/")' will open "symlink" even when "symlink" is a symbolic link pointing outside of the root.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-97032?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--97032" src="https://img.shields.io/badge/CVE--2026--97032-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.676%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>53rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

HTTP/2 servers could end up crashing due to inadvertently modifying its HPACK encoder concurrently. This happens because the server modifies the HPACK encoder from two goroutines without synchronization: one uses the encoder to encode a HEADERS frame as part of a response sent to a client and the other modifies the encoder's table size when handling a SETTINGS frame containing SETTINGS_HEADER_TABLE_SIZE that a client sends. A malicious client can repeatedly send a request while changing the header table size to crash the server.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-97031?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--97031" src="https://img.shields.io/badge/CVE--2026--97031-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.716%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>54th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Multiple ECH outer extension references are not permitted under RFC 9849; previously, a client could send a well-crafted packet that could trigger memory exhaustion in the server process by specifying multiple references.

We now reject these as malformed and curb the memory amplification vector as a result.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-94440?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--94440" src="https://img.shields.io/badge/CVE--2026--94440-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.706%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>54th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Parsing a multipart form can bypass memory limits and read an arbitrarily long line into memory when the remaining limit at the start of a part is less than 400 bytes.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-94439?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--94439" src="https://img.shields.io/badge/CVE--2026--94439-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.528%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When an HTTP server handler sends a 2xx response to an HTTP/1 CONNECT request and returns without hijacking the connection, the server improperly continues to read and serve requests from the connection. Since a 2xx response to an HTTP/1 CONNECT converts the connection into a tunnel, the server should not treat the connection as continuing to contain HTTP.

The impact of this misbehavior is mostly limited to potential request smuggling, where an intermediate proxy considers the data on the connection to be tunneled and the server considers it to be HTTP.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78669?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--78669" src="https://img.shields.io/badge/CVE--2026--78669-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.847%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>59th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A malicious HTTP/2 peer can cause excessive CPU consumption in the client or server by opening a large number of streams and then sending many small SETTINGS frames containing SETTINGS_INITIAL_WINDOW_SIZE values.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78667?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--78667" src="https://img.shields.io/badge/CVE--2026--78667-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.663%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>52nd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When parsing a Range header containing a large number of small ranges, FileServer(FS), ServeContent, and ServeFile(FS) can consume an excessive amount of CPU.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78660?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--78660" src="https://img.shields.io/badge/CVE--2026--78660-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.542%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>46th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Historically, we have been rather lax about malformed framing-related headers in our HTTP/2 implementation, as they cannot interfere with HTTP/2 framing. However, this makes it possible for our HTTP/2 implementation to forward responses containing such headers to an HTTP/1 client when acting as a reverse proxy. If the HTTP/1 client also does not behave strictly enough, this can result in response smuggling.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78659?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--78659" src="https://img.shields.io/badge/CVE--2026--78659-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.866%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>59th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When "Trailer" headers are sent by a client, the HTTP server internally uses the header values to populate the Request.Trailer map passed to the server handler. Because Request.Trailer is a map, each entry incurs memory overhead. For HTTP/2 servers, a malicious client can exploit this by sending a "Trailer" header that declares a large number of fields, causing the server to allocate a disproportionate amount of memory while bypassing Server.MaxHeaderValueCount and Server.MaxHeaderBytes limits. This exploit is not applicable for HTTP/1 servers, which do not support multiplexing a large number of requests over one TCP connection, and whose Server.MaxHeaderBytes are calculated differently.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56866?s=golang&n=stdlib&t=golang&vr=%3C1.26.9"><img alt="high : CVE--2026--56866" src="https://img.shields.io/badge/CVE--2026--56866-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.26.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.26.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.604%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>49th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When http.Transport sends an HTTP/1 CONNECT request with a non-empty Request.Body, it writes the body directly to the connection without framing after the request headers. If the server rejects the CONNECT request with a non-2xx keep-alive response, Transport returns the connection to the idle pool. Because CONNECT requests do not have a request body, the server may interpret the trailing body bytes as a subsequent pipelined HTTP/1.1 request on the connection, leaving the pooled connection desynchronized and causing the next caller that reuses it to read the response to the injected request. In reverse proxies (including httputil.ReverseProxy) that forward CONNECT requests through a shared Transport, this can lead to cross-user response poisoning.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56862?s=golang&n=stdlib&t=golang&vr=%3C1.25.13"><img alt="high : CVE--2026--56862" src="https://img.shields.io/badge/CVE--2026--56862-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.13</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.13</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.568%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>48th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Handshake messages, such as KeyUpdate, are always considered as state-advancing, regardless of whether a handshake has been completed or not. As a result, a malicious client can keep sending KeyUpdate messages to force the server to keep performing key derivation operations indefinitely.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56859?s=golang&n=stdlib&t=golang&vr=%3C1.25.13"><img alt="high : CVE--2026--56859" src="https://img.shields.io/badge/CVE--2026--56859-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.13</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.13</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.568%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>48th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Previously, DecodeElement would reset the depth counter causing it to never fire; this could lead to stack exhaustion.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56853?s=golang&n=stdlib&t=golang&vr=%3C1.25.13"><img alt="high : CVE--2026--56853" src="https://img.shields.io/badge/CVE--2026--56853-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.13</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.13</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.568%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>48th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When a server is configured to support unencrypted HTTP/2, it reads a few bytes from each new connection to see if they contain the HTTP/2 client preface. ReadHeaderTimeout is unexpectedly not being applied when doing this.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-42504?s=golang&n=stdlib&t=golang&vr=%3C1.25.11"><img alt="high : CVE--2026--42504" src="https://img.shields.io/badge/CVE--2026--42504-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.11</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.11</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.560%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>47th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Decoding a maliciously-crafted MIME header containing many invalid encoded-words can consume excessive CPU.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-42499?s=golang&n=stdlib&t=golang&vr=%3C1.25.10"><img alt="high : CVE--2026--42499" src="https://img.shields.io/badge/CVE--2026--42499-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.10</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.10</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.798%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>57th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Pathological inputs could cause DoS through consumePhrase when parsing an email address according to RFC 5322.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39836?s=golang&n=stdlib&t=golang&vr=%3C1.25.10"><img alt="high : CVE--2026--39836" src="https://img.shields.io/badge/CVE--2026--39836-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.10</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.10</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.633%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>51st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The Dial and LookupPort functions panic on Windows when provided with an input containing a NUL (0).

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-39820?s=golang&n=stdlib&t=golang&vr=%3C1.25.10"><img alt="high : CVE--2026--39820" src="https://img.shields.io/badge/CVE--2026--39820-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.10</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.10</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.784%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>57th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Well-crafted inputs reaching ParseAddress, ParseAddressList, and ParseDate were able to trigger excessive CPU exhaustion and memory allocations.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-33818?s=golang&n=stdlib&t=golang&vr=%3C1.25.13"><img alt="high : CVE--2026--33818" src="https://img.shields.io/badge/CVE--2026--33818-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.13</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.13</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.568%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>48th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Enforce a recursion limit in Unmarshal to prevent stack exhaustion when parsing deeply-nested, recursive structures.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-33814?s=golang&n=stdlib&t=golang&vr=%3C1.25.10"><img alt="high : CVE--2026--33814" src="https://img.shields.io/badge/CVE--2026--33814-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.10</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.10</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.840%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>58th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When processing HTTP/2 SETTINGS frames, transport will enter an infinite loop of writing CONTINUATION frames if it receives a SETTINGS_MAX_FRAME_SIZE with a value of 0.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-33811?s=golang&n=stdlib&t=golang&vr=%3C1.25.10"><img alt="high : CVE--2026--33811" src="https://img.shields.io/badge/CVE--2026--33811-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.10</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.10</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.875%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>60th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When using LookupCNAME with the cgo DNS resolver, a very long CNAME response can trigger a double-free of C memory and a crash.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-32283?s=golang&n=stdlib&t=golang&vr=%3C1.25.9"><img alt="high : CVE--2026--32283" src="https://img.shields.io/badge/CVE--2026--32283-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.632%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>51st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

If one side of the TLS connection sends multiple key update messages post-handshake in a single record, the connection can deadlock, causing uncontrolled consumption of resources. This can lead to a denial of service.

This only affects TLS 1.3.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-32281?s=golang&n=stdlib&t=golang&vr=%3C1.25.9"><img alt="high : CVE--2026--32281" src="https://img.shields.io/badge/CVE--2026--32281-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.361%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>30th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Validating certificate chains which use policies is unexpectedly inefficient when certificates in the chain contain a very large number of policy mappings, possibly causing denial of service.

This only affects validation of otherwise trusted certificate chains, issued by a root CA in the VerifyOptions.Roots CertPool, or in the system certificate pool.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-32280?s=golang&n=stdlib&t=golang&vr=%3C1.25.9"><img alt="high : CVE--2026--32280" src="https://img.shields.io/badge/CVE--2026--32280-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.9</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.9</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.626%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>51st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

During chain building, the amount of work that is done is not correctly limited when a large number of intermediate certificates are passed in VerifyOptions.Intermediates, which can lead to a denial of service. This affects both direct users of crypto/x509 and users of crypto/tls.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-25679?s=golang&n=stdlib&t=golang&vr=%3C1.25.8"><img alt="high : CVE--2026--25679" src="https://img.shields.io/badge/CVE--2026--25679-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.25.8</code></td></tr>
<tr><td>Fixed version</td><td><code>1.25.8</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.827%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>58th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

url.Parse insufficiently validated the host/authority component and accepted some invalid URLs.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 3" src="https://img.shields.io/badge/C-3-8b1924"/> <img alt="high: 7" src="https://img.shields.io/badge/H-7-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>github.com/rabbitmq/amqp091-go</strong> <code>1.10.0</code> (golang)</summary>

<small><code>pkg:golang/github.com/rabbitmq/amqp091-go@1.10.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-77411?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="critical 9.5: CVE--2026--77411" src="https://img.shields.io/badge/CVE--2026--77411-lightgrey?label=critical%209.5&labelColor=8b1924"/></a> <i>Improper Check for Unusual or Exceptional Conditions</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.524%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

**Summary**

A critical stream desynchronization vulnerability has been identified in the AMQP wire-protocol parser. When parsing a long string (`readLongstr`) within a table field, providing a length that exceeds the maximum signed 32-bit integer (`2^31 - 1`, or roughly `2.1` GiB) triggers an improper error-handling condition. The parser abruptly aborts the read and returns a success status (`"",nil`) without consuming the specified bytes from the underlying network buffer. This causes all subsequent read operations to become misaligned. The parser interprets arbitrary offsets within the remaining payload bytes as valid AMQP frame headers, leading to potential Remote Code Execution (RCE), data injection, or complete connection hijacking.

**Vulnerability Details**

The vulnerability exists within the bounds-checking logic of the readLongstr function:
```go
// read.go:113-114 — silent no-op return, bytes left in stream
if length > (^uint32(0) >> 1) {
    return  // returns "", nil, does NOT consume `length` bytes
}
```
When `length` evaluates to a value greater than `0x7FFFFFFF`:

1. The function executes a silent `return` statement.
2. Because Go utilizes named or zero-value initialization for unassigned return registers, this yields `"", nil` (indicating a successful read of an empty string).
3. The Critical Failure: The reader's cursor is not advanced by `length` bytes. The malformed payload remains sitting in the TCP/buffer stream.

**Impact**

As `readTable` continues iterating over the stream under the assumption that the string was successfully parsed, the byte alignment is entirely broken.

- Parser Desynchronization: Future AMQP frame headers are read from arbitrary offsets inside the attacker-controlled message payload.
- Payload Reinterpretation: A malicious actor can carefully craft the trailing bytes of the initial payload to perfectly mimic valid AMQP frames (e.g., `connection.close`, `channel.open`, or message publishing frames), forcing the client/server to execute unintended actions.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77405?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="critical 9.4: CVE--2026--77405" src="https://img.shields.io/badge/CVE--2026--77405-lightgrey?label=critical%209.4&labelColor=8b1924"/></a> <i>Cleartext Storage of Sensitive Information in Memory</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.4</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:N/VC:H/VI:H/VA:N/SC:H/SI:L/SA:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.282%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>21st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary
A structural security weakness exists in the AMQP client's TLS configuration generator (`tlsConfigFromURI`). When constructing a `*tls.Config` object from an `amqps://` connection URI, the library initializes the structure without explicitly defining the `MinVersion` field. 

While modern versions of the Go compiler toolchain (Go 1.18+) default the implicit minimum version to TLS 1.2, this security posture relies entirely on an implicit toolchain dependency. If the library is compiled using legacy Go toolchains (Go < 1.18), or if a future toolchain introduces fallback behavior, the client could silently negotiate obsolete and insecure TLS 1.0 or TLS 1.1 protocols during connection handshakes with a compromised or malicious AMQP broker.

---

## Vulnerability Details

### Mechanism
The vulnerability lies in the lack of an explicit safety floor when assigning configurations inside the URI component:

```go
// Example within uri.go's tlsConfigFromURI
cfg := &tls.Config{
    ServerName: host,
    // MinVersion is left completely unassigned (defaults to 0, or toolchain default)
}
```

In the Go standard library (`crypto/tls`), leaving `MinVersion: 0` instructs the runtime to choose the toolchain's default minimum. Prior to Go 1.18, this default allowed negotiation down to TLS 1.0. Relying on implicit compiler configurations violates secure coding practices by decoupling the library's security posture from its source code, leaving applications vulnerable based solely on how they are built.

### Impact
If a client application is built with a legacy compiler environment or a custom Go runtime, an attacker capable of executing a Man-in-the-Middle (MitM) attack can force the connection to downgrade to TLS 1.0 or 1.1. This exposes the AMQP protocol data stream to well-known cryptographic vulnerabilities (such as BEAST, POODLE, or SWEET32), allowing the attacker to decrypt or alter message payloads, connection parameters, and authentication credentials.

---

## Attack Vector
An attacker performing a network-level downgrade attack can intercept a client connection built under a legacy toolchain:

1. **Interception:** A client application compiled on a legacy pipeline attempts to establish an encrypted connection to an AMQP broker.
2. **Protocol Downgrade:** The attacker intercepts the TLS Client Hello handshake and forces a downgrade negotiation to TLS 1.0.
3. **Cryptographic Exploitation:** Because `MinVersion` was never explicitly locked to `tls.VersionTLS12` by the library, the client accepts the weak cipher suites, allowing the attacker to monitor or manipulate the underlying AMQP session data.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77408?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="critical 9.1: CVE--2026--77408" src="https://img.shields.io/badge/CVE--2026--77408-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Integer Overflow or Wraparound</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:L/VI:H/VA:H/SC:L/SI:H/SA:L</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.524%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary
A data integrity and protocol corruption vulnerability exists in the AMQP client's property serialization logic. When encoding AMQP short string (`shortstr`) fields—such as identifiers, routing strings, and content metadata—the length of the string is explicitly cast to a fixed-size 8-bit unsigned integer (`uint8`). 

If an application provides a property string exceeding 255 bytes, the length counter silently wraps around (e.g., a length of 300 wraps to 44). As a result, the parser writes only a truncated portion of the string into the outgoing connection buffer without returning an error. This leads to silent data corruption, broken RPC routing, and unpredictable broker-side state behavior.

---

## Vulnerability Details

### Mechanism
The vulnerability resides in the wire-level serialization logic for application publishing properties:

```go
// write.go:246
length := uint8(len(b))  // wraps silently when len(b) > 255 (e.g., 300 -> 44)
```

Because Go allows silent integer truncation during explicit type casting, lengths larger than $2^8 - 1$ lose their most significant bits. The underlying stream writer reads `length` to determine how many bytes to pull from the buffer. Because no error or boundary check accompanies this truncation, the application believes the full payload was transmitted successfully.

### Affected Properties
This truncation behavior affects every standard AMQP field serialized as a `shortstr`:
* `CorrelationId`
* `ReplyTo`
* `MessageId`
* `Expiration`
* `UserId`
* `AppId`
* `ContentType`
* `ContentEncoding`
* `Type`

### Impact
The critical consequence is **silent protocol desynchronization at the application layer**. The underlying TCP stream remains framed properly (because the shortened length matches the bytes written), but the business logic is corrupted. Distributed transactions, request-reply correlations, and tracing headers are truncated, causing downstream systems to drop messages or route them to incorrect consumers.

---

## Attack Vector
An attacker who can influence metadata fields processed by an upstream application (such as a user-supplied tracking ID or a long content-type header) can exploit this to break system components:

1. **Targeting RPC Routing:** A user passes a malicious or overly long `CorrelationId` of 300 bytes through an application endpoint.
2. **Silent Truncation:** The library wraps the length value to 44, transmitting only the first 44 bytes to the rabbitMQ broker.
3. **Broken Correlation:** When the service processes the request and responds, the replying consumer attempts to route the message using the full 300-byte identifier. Because the broker only recognizes the truncated 44-byte ID, the reply loop breaks silently, leading to hanging processes or data leaks across transaction boundaries.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-79921?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 8.9: CVE--2026--79921" src="https://img.shields.io/badge/CVE--2026--79921-lightgrey?label=high%208.9&labelColor=e25d68"/></a> <i>Allocation of Resources Without Limits or Throttling</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.9</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.550%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>47th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

**Summary**
A vulnerability exists in the amqp091-go client library where a compromised or malicious AMQP broker can force the client to allocate resources for and process content body frames that exceed the negotiated frame_max limit. This can lead to unexpected memory consumption or application-layer denial of service (DoS), bypassing the protocol's built-in framing constraints.

**Details**
During a standard AMQP 0-9-1 connection handshake, the client and the broker negotiate a maximum frame size (frame_max), for example, 4096 bytes.

However, after negotiation, a malicious broker can send a valid basic.deliver sequence containing a content body frame whose header declares a payload size larger than the negotiated frame_max. Instead of enforcing the agreed-upon limit and closing the connection with a frame-error (as mandated by the AMQP 0-9-1 specification), the amqp091-go client:

1. Accepts the broker-declared oversized frame size.
2. Allocates memory based on this oversized declaration.
3. Reads the payload, assembles it into the message, and delivers it to the consumer.

**Impact**

- Denial of Service (DoS): If a broker sends extremely large frame sizes, it can trigger significant memory allocations on the client side, potentially leading to Out-Of-Memory (OOM) crashes.
- Protocol Violation: The client fails to enforce negotiated connection parameters, trusting the broker implicitly even after constraints have been established.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77412?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 8.9: CVE--2026--77412" src="https://img.shields.io/badge/CVE--2026--77412-lightgrey?label=high%208.9&labelColor=e25d68"/></a> <i>Incorrect Conversion between Numeric Types</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.9</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.524%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

**Summary**
A vulnerability in the readField function allows a malicious or compromised AMQP server to trigger an unhandled runtime panic in the client application, leading to an immediate crash of the entire process.

**Details**
When parsing incoming AMQP frames, the `readField` function processes byte-array fields (type tag `'x'`) by reading a 32-bit big-endian integer to determine the length of the data payload.

```go
// read.go:253-263
case 'x':
    var len int32
    if err = binary.Read(r, binary.BigEndian, &len); err != nil {
        return nil, err
    }
    value := make([]byte, len)  // PANICS if len < 0
```

If a server transmits a length value of `0xFFFFFFFF`, it is interpreted by the client as a signed 32-bit integer with a value of `-1`. Passing a negative integer to Go's built-in make() function for slice allocation triggers an unrecoverable runtime panic (panic: len out of range).

Because the reader goroutine handles network I/O without an explicit recover() wrapper, this panic propagates up to the runtime root, abruptly terminating the host application.

**Attack Vector / Exploitation Scenario**
An attacker capable of spoofing, compromising, or controlling an AMQP broker can exploit this flaw during two primary phases:

1. Connection Establishment: Sending a malicious connection.start handshake frame containing server-properties with an 'x' type field assigned a negative length.
2. Message Delivery: Delivering a message payload where the header table contains a malformed field matching the criteria above.

**Impact**
Availability: High. A single malformed frame can reliably crash the client process, resulting in a persistent Denial of Service (DoS) if the client automatically reconnects and receives the same payload.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77410?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 8.9: CVE--2026--77410" src="https://img.shields.io/badge/CVE--2026--77410-lightgrey?label=high%208.9&labelColor=e25d68"/></a> <i>Memory Allocation with Excessive Size Value</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.9</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.524%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

**Summary**
A flaw in the `recvContent` function allows a malicious AMQP server to trigger an Out-of-Memory (OOM) error, forcing the host operating system or container runtime to immediately terminate the client process.

**Vulnerability Details**
When receiving message content payloads, the client processes the expected size from the content header framework. The `recvContent` function attempts to optimize performance by pre-allocating memory for the message body based on the `ch.header.Size` field, which is a 64-bit unsigned integer (`uint64`).

```go
// channel.go:495-496
if cap(ch.body) == 0 {
    ch.body = make([]byte, 0, ch.header.Size)  // unbounded
}
```

The underlying library fails to validate or cap this requested size against any upper boundary—such as the maximum frame size negotiated during connection establishment (`FrameMax`). If a server specifies an extreme body size (e.g., `2^62` bytes), the Go runtime attempts to allocate an exabyte-scale slice capacity. This immediately exhausts available system memory, causing the operating system's OOM killer to terminate the application.

**Attack Vector / Exploitation Scenario**

- Message Delivery Phase: A malicious or compromised AMQP broker sends a standard `basic.deliver` frame containing a content header with an intentionally inflated `body-size` variable.
- Authentication Requirement: No special privileges or authentication bypasses are required; the crash occurs seamlessly during normal message consumption.

**Impact**

- Availability: High. Exploded memory consumption results in an instant process termination, destroying application state and availability for all threads sharing the environment.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77403?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 8.9: CVE--2026--77403" src="https://img.shields.io/badge/CVE--2026--77403-lightgrey?label=high%208.9&labelColor=e25d68"/></a> <i>Allocation of Resources Without Limits or Throttling</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.9</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.524%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary
A Denial of Service (DoS) vulnerability exists in the AMQP client's connection negotiation logic. The AMQP specification explicitly mandates a strict minimum frame size of 4096 bytes to prevent pathological packet fragmentation. While the library defines a `frameMinSize = 4096` constant, the connection negotiation loop fails to enforce this boundary, blindly accepting whatever maximum frame size (`FrameMax`) the server advertises during the handshake.

If a client connects to a malicious or compromised AMQP broker that advertises an extremely low `FrameMax` (such as 1 byte), the negotiation succeeds. Consequently, every subsequent message transmission is forced to splinter into thousands or millions of single-byte frames, causing massive CPU overhead, thread contention, and a near-instantaneous application freeze.

---

## Vulnerability Details

### Mechanism
During the connection establishment phase, the client and server negotiate connection parameters—including maximum channel count, heartbeat intervals, and maximum frame sizes. The vulnerability is located where the client accepts the server's tuning parameters:

```go
// Connection negotiation logic maps server values directly without validation
if serverSettings.FrameMax > 0 {
    // VULNERABILITY: Lacks a floor validation check against frameMinSize (4096)
    c.config.FrameMax = serverSettings.FrameMax 
}
```

Because there is no conditional check asserting that `serverSettings.FrameMax >= frameMinSize`, a value below the protocol specification floor is successfully registered. When the application later passes data payloads to the frame writer, the chunking algorithm splits the payload using the negotiated `FrameMax` value as its chunk window divisor.

### Impact
When `FrameMax` is set to an absurdly low threshold (e.g., 1 to 10 bytes):
* A standard 10 KiB message payload requires tens of thousands of individual write operations and frame headers.
* The system's CPU becomes entirely bound by frame serialization, memory allocation for frame structures, and context switching within the network output loops.
* This results in an application-layer Denial of Service (DoS) affecting not just the specific AMQP connection, but potentially the entire host system due to CPU resource starvation.

---

## Attack Vector
An attacker who compromises an upstream AMQP broker, performs a Man-in-the-Middle (MitM) interception, or tricks an application into connecting to an unauthorized external rogue broker can trigger this vulnerability:

1. **Rogue Handshake:** The client application connects to an AMQP endpoint controlled by the attacker.
2. **Malicious Parameter Tuning:** During the `connection.tune` phase, the rogue server returns a `FrameMax` value of `1`.
3. **Resource Exhaustion Trigger:** The client completes the handshake successfully. As soon as the client attempts to publish a message or process traffic, the internal loop fragments the data into single-byte frames, spiking the host's CPU usage to 100% and disabling the application thread.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77404?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 8.7: CVE--2026--77404" src="https://img.shields.io/badge/CVE--2026--77404-lightgrey?label=high%208.7&labelColor=e25d68"/></a> <i>Improper Encoding or Escaping of Output</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:L/AC:L/AT:P/PR:L/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:L</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.104%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>1st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary
A query parameter injection vulnerability exists in the AMQP client's connection URI formatting logic. When generating or parsing connection URIs, TLS-related filesystem paths (such as certificates or keys) are appended directly to the URI's query string using string concatenation rather than secure URL encoding via functions like `url.QueryEscape`.

If an application handles a TLS file path containing special character delimiters (such as `&` or `=`), these characters are interpreted as parameter separators by the URI parser. If the resulting `URI.String()` output is subsequently re-parsed via `ParseURI`, the injected fields can silently overwrite or hijack critical configuration parameters, forcing the client to use arbitrary connection settings or alternate TLS files.

---

## Vulnerability Details

### Mechanism
The vulnerability lies within the lack of proper escaping when compiling connection string components into a raw URL format:

```go
// Example of insecure string concatenation during URI building
uri := fmt.Sprintf("amqps://user:pass@<!-- -->host/%s?certfile=%s&keyfile=%s", vhost, certPath, keyPath)
```

Because `certPath` and `keyPath` are not passed through `url.QueryEscape`, special URL characters preserve their control meanings. For instance, if a user supply a certificate path named:
`/tmp/cert=foo&keyfile=/evil/path`

The generated string translates into:
`...?certfile=/tmp/cert=foo&keyfile=/evil/path&keyfile=/original/path`

When this string passes back through `ParseURI` (common in connection re-dial routines or configuration replication steps), standard URL parsing mechanics treat the string as multiple distinct parameters. Depending on map assignment order inside the parser, the injected keys take precedence over the original parameters.

### Impact
By manipulating the file paths used for TLS assets, an attacker or compromised local sub-system can:
* Inject arbitrary alternative options or override protocol settings.
* Substitute or switch keyfiles, leading to connection failures or the parsing of unauthorized cryptographic assets.
* Corrupt connection state variables, triggering application-layer failures during connection setup or recovery.

---

## Attack Vector
An attacker who has partial control over directory naming conventions or environmental variables used to specify local infrastructure paths can execute a parameter injection attack:

1. **Path Creation:** An attacker sets up a path containing deliberate URL parameter delimiters (e.g., `/var/lib/certs/client.crt?cacertfile=/tmp/fake_ca.crt&`).
2. **String Generation:** The application serializes the active connection state or passes the paths down to an unescaped URI builder function.
3. **Configuration Hijack:** The URI string is generated with the injected parameter embedded into the query structure. When the client attempts to reuse or re-parse this connection string during a connection retry or worker spin-up, it parses the injected `cacertfile` parameter, loading a different, unverified Certificate Authority string.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77406?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 8.2: CVE--2026--77406" src="https://img.shields.io/badge/CVE--2026--77406-lightgrey?label=high%208.2&labelColor=e25d68"/></a> <i>Signed to Unsigned Conversion Error</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.2</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:L</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.524%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>45th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary
A logic and resource exhaustion vulnerability exists in the AMQP client's Quality of Service (`Qos`) configuration method. The `Qos` function accepts signed integers (`int`) for the `prefetchCount` and `prefetchSize` parameters but casts them directly to unsigned integers (`uint16` and `uint32`, respectively) when formatting the wire-level frame.

If a developer passes a negative integer (such as `-1`) to these parameters—frequently intended as a sentinel value meaning "no change" or "no limit"—the application performs an implicit signed-to-unsigned conversion. This wraps the values to their absolute maximum limit ($65535$ and $4294967295$). Consequently, a consumer expecting restricted message delivery rates is suddenly flooded with an unlimited volume of messages, potentially exhausting memory resources and crashing the application.

---

## Vulnerability Details

### Mechanism
The bug manifests during the structural assignment inside the channel's `Qos` method:

```go
// channel.go:795-796
PrefetchCount: uint16(prefetchCount),  // -1 wraps to 65535
PrefetchSize:  uint32(prefetchSize),   // -1 wraps to 4294967295
```

In Go, converting a negative signed integer to an unsigned integer shifts the value via two's complement arithmetic. Because no boundary validation or signedness check occurs prior to the cast:
* Passing `-1` for `prefetchCount` yields a wire value of `65535`.
* Passing `-1` for `prefetchSize` yields a wire value of `4294967295`.

### Impact
The AMQP broker interprets a `prefetch-count` of `65535` as an instruction to dispatch messages to the consumer with virtually no concurrency limits. 

If the application is processing heavy payloads or relies on strict rate-limiting to maintain stability, this unexpected flood will cause rapid heap memory growth, unmanageable processing queues, and an eventual Out-Of-Memory (OOM) termination.

---

## Attack Vector
An attacker who can manipulate configuration files, environmental variables, or API inputs that dictate client Qos settings can trigger an application-layer Denial of Service:

1. **Malicious Input:** An attacker sets a service's prefetch configuration parameter to `-1`.
2. **Implicit Overflow:** The application initializes the channel, executes `Qos(-1, ...)`, and transmits an unintended maximum-capacity request to the RabbitMQ/AMQP broker.
3. **Consumer Exhaustion:** The broker flushes the entire contents of the queue directly into the client consumer's network buffer, bypassing expected application concurrency barriers and inducing a crash.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-77407?s=github&n=amqp091-go&ns=github.com%2Frabbitmq&t=golang&vr=%3C1.13.0"><img alt="high 7.0: CVE--2026--77407" src="https://img.shields.io/badge/CVE--2026--77407-lightgrey?label=high%207.0&labelColor=e25d68"/></a> <i>Cleartext Storage of Sensitive Information in Memory</i>

<table>
<tr><td>Affected range</td><td><code><1.13.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.13.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:L/AC:L/AT:P/PR:L/UI:N/VC:H/VI:N/VA:N/SC:H/SI:L/SA:L</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.131%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>3rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary
An information disclosure vulnerability exists in the AMQP client implementation's authentication handling configuration. Following a successful connection handshake, the `Connection.Config.SASL` field stores the `Authentication` implementation state used to establish the session. 

For standard `PLAIN` authentication, this state utilizes the `PlainAuth` struct, which defines both `Username` and `Password` as publicly exported, plaintext string fields. Because this sensitive data is retained permanently in-memory within an exported field structure, any peripheral code, internal package, reflective logger, dependency, or automated debugging utility with access to the core `*Connection` object can read and expose the raw credentials.

---

## Vulnerability Details

### Mechanism
The vulnerability stems from the structural design of the configuration storage used during and after the AMQP handshake:

```go
// auth.go:21-23
type PlainAuth struct {
    Username string
    Password string  // exported plaintext
}
```

When an application initializes a connection, the `PlainAuth` object is deeply nested inside the configuration structure (`Connection.Config`). Even after the handshake concludes and authentication is complete, this structure persists natively in-memory for the duration of the network connection's lifecycle. 

Because `Password` is an exported string field, standard automated inspection mechanisms can read its value without restriction.

### Affected Code Paths & Integrations
Any sub-component or library that traverses or reads the `*Connection` object will inadvertently read the plaintext password, including:
* **Reflective Loggers:** Structured logging frameworks that serialize nested configuration structs into JSON/Log formats.
* **APM & Performance Agents:** Automated telemetry or Application Performance Monitoring tools that capture state snapshots.
* **Debugging & Panic Handlers:** Mid-tier software or dump libraries designed to capture goroutine state or print deep struct hierarchies upon program errors or signals.

### Impact
The credential remains vulnerable to leak paths into logging pipelines, log aggregators, security information and event management (SIEM) systems, or standard output. Once transmitted to external log infrastructure, these credentials become accessible to unprivileged operators or any actor with access to log archives.

---

## Attack Vector
An attacker does not necessarily need direct remote code execution to exploit this flaw; instead, the vulnerability acts as a credential harvesting vector inside multi-tenant environments or via secondary log exposure:

1. **Configuration Dump:** An operator configures a standard reflective logger or third-party APM package to capture system state parameters, including the active AMQP `*Connection` object.
2. **Reflective Access:** The inspection engine uses Go's `reflect` package to walk the structural hierarchy, pulling the string value from `Connection.Config.SASL.(*PlainAuth).Password`.
3. **Exfiltration:** The plaintext password is written to standard system logs, which are then scraped into shared logging aggregators, exposing production infrastructure credentials to a wider audience.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 2" src="https://img.shields.io/badge/C-2-8b1924"/> <img alt="high: 7" src="https://img.shields.io/badge/H-7-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>golang.org/x/net</strong> <code>0.39.0</code> (golang)</summary>

<small><code>pkg:golang/golang.org/x/net@0.39.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-39821?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.55.0"><img alt="critical : CVE--2026--39821" src="https://img.shields.io/badge/CVE--2026--39821-lightgrey?label=critical%20&labelColor=8b1924"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.55.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.55.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.834%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>79th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The ToASCII and ToUnicode functions incorrectly accept Punycode-encoded labels that decode to an ASCII-only label. For example, ToUnicode("xn--example-.com") incorrectly returns the name "example.com" rather than an error.

This behavior can lead to privilege escalation in programs using the idna package. For example, a program which performs privilege checks on the ASCII hostname may reject "example.com" but permit "xn--example-.com". If that program subsequently converts the ASCII hostname to Unicode, it will inadvertently permits access to the Unicode name "example.com".

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78663?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.60.0"><img alt="critical : CVE--2026--78663" src="https://img.shields.io/badge/CVE--2026--78663-lightgrey?label=critical%20&labelColor=8b1924"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.60.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.60.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.858%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>59th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The HTTP/2 server can refund connection-level flow control twice for the same data: Once when a client resets a stream (refunding data for any sent-but-unread portion of the stream), and again when a request handler reads the buffered data. A malicious client can exploit this to bypass the configured connection-level flow control limit (MaxReceiveBufferPerConnection). Total buffered data is still limited by the concurrent stream limit and stream-level flow control.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-97032?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.60.0"><img alt="high : CVE--2026--97032" src="https://img.shields.io/badge/CVE--2026--97032-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.60.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.60.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.676%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>53rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

HTTP/2 servers could end up crashing due to inadvertently modifying its HPACK encoder concurrently. This happens because the server modifies the HPACK encoder from two goroutines without synchronization: one uses the encoder to encode a HEADERS frame as part of a response sent to a client and the other modifies the encoder's table size when handling a SETTINGS frame containing SETTINGS_HEADER_TABLE_SIZE that a client sends. A malicious client can repeatedly send a request while changing the header table size to crash the server.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78669?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.60.0"><img alt="high : CVE--2026--78669" src="https://img.shields.io/badge/CVE--2026--78669-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.60.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.60.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.847%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>59th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A malicious HTTP/2 peer can cause excessive CPU consumption in the client or server by opening a large number of streams and then sending many small SETTINGS frames containing SETTINGS_INITIAL_WINDOW_SIZE values.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78661?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.62.0"><img alt="high : CVE--2026--78661" src="https://img.shields.io/badge/CVE--2026--78661-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.62.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.62.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.409%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>36th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When coalescing adjacent text nodes in addText and fosterParent, appending to an existing TextNode's Data via string concatenation (n.Data += text) reallocated and copied the accumulated string on every token. Inputs containing many short text runs separated by ignored end tags (such as "a</x>") caused O(n^2) allocations and byte copies.

Accumulate coalesced text in per-node byte slices during parsing and materialize Data strings once at the end of parse.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78660?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.60.0"><img alt="high : CVE--2026--78660" src="https://img.shields.io/badge/CVE--2026--78660-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.60.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.60.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.542%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>46th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Historically, we have been rather lax about malformed framing-related headers in our HTTP/2 implementation, as they cannot interfere with HTTP/2 framing. However, this makes it possible for our HTTP/2 implementation to forward responses containing such headers to an HTTP/1 client when acting as a reverse proxy. If the HTTP/1 client also does not behave strictly enough, this can result in response smuggling.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-78659?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.60.0"><img alt="high : CVE--2026--78659" src="https://img.shields.io/badge/CVE--2026--78659-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.60.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.60.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.866%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>59th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When "Trailer" headers are sent by a client, the HTTP server internally uses the header values to populate the Request.Trailer map passed to the server handler. Because Request.Trailer is a map, each entry incurs memory overhead. For HTTP/2 servers, a malicious client can exploit this by sending a "Trailer" header that declares a large number of fields, causing the server to allocate a disproportionate amount of memory while bypassing Server.MaxHeaderValueCount and Server.MaxHeaderBytes limits. This exploit is not applicable for HTTP/1 servers, which do not support multiplexing a large number of requests over one TCP connection, and whose Server.MaxHeaderBytes are calculated differently.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-46600?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.56.0"><img alt="high : CVE--2026--46600" src="https://img.shields.io/badge/CVE--2026--46600-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.56.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.56.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.549%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>47th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Parsing an invalid SVCB or HTTPS RR can panic when the size of a parameter value overflows the message buffer.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-33814?s=golang&n=net&ns=golang.org%2Fx&t=golang&vr=%3C0.53.0"><img alt="high : CVE--2026--33814" src="https://img.shields.io/badge/CVE--2026--33814-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.53.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.53.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.840%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>58th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

When processing HTTP/2 SETTINGS frames, transport will enter an infinite loop of writing CONTINUATION frames if it receives a SETTINGS_MAX_FRAME_SIZE with a value of 0.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 1" src="https://img.shields.io/badge/C-1-8b1924"/> <img alt="high: 3" src="https://img.shields.io/badge/H-3-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>google.golang.org/grpc</strong> <code>1.72.0</code> (golang)</summary>

<small><code>pkg:golang/google.golang.org/grpc@1.72.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-33186?s=github&n=grpc&ns=google.golang.org&t=golang&vr=%3C1.79.3"><img alt="critical 9.1: CVE--2026--33186" src="https://img.shields.io/badge/CVE--2026--33186-lightgrey?label=critical%209.1&labelColor=8b1924"/></a> <i>Improper Authorization</i>

<table>
<tr><td>Affected range</td><td><code><1.79.3</code></td></tr>
<tr><td>Fixed version</td><td><code>1.79.3</code></td></tr>
<tr><td>CVSS Score</td><td><code>9.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.619%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>76th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact
_What kind of vulnerability is it? Who is impacted?_

It is an **Authorization Bypass** resulting from **Improper Input Validation** of the HTTP/2 `:path` pseudo-header.

The gRPC-Go server was too lenient in its routing logic, accepting requests where the `:path` omitted the mandatory leading slash (e.g., `Service/Method` instead of `/Service/Method`). While the server successfully routed these requests to the correct handler, authorization interceptors (including the official `grpc/authz` package) evaluated the raw, non-canonical path string. Consequently, "deny" rules defined using canonical paths (starting with `/`) failed to match the incoming request, allowing it to bypass the policy if a fallback "allow" rule was present.

**Who is impacted?**
This affects gRPC-Go servers that meet both of the following criteria:
1. They use path-based authorization interceptors, such as the official RBAC implementation in `google.golang.org/grpc/authz` or custom interceptors relying on `info.FullMethod` or `grpc.Method(ctx)`.
2. Their security policy contains specific "deny" rules for canonical paths but allows other requests by default (a fallback "allow" rule).

The vulnerability is exploitable by an attacker who can send raw HTTP/2 frames with malformed `:path` headers directly to the gRPC server.

### Patches
_Has the problem been patched? What versions should users upgrade to?_

Yes, the issue has been patched. The fix ensures that any request with a `:path` that does not start with a leading slash is immediately rejected with a `codes.Unimplemented` error, preventing it from reaching authorization interceptors or handlers with a non-canonical path string.

Users should upgrade to the following versions (or newer):
* **v1.79.3**
* The latest **master** branch.

It is recommended that all users employing path-based authorization (especially `grpc/authz`) upgrade as soon as the patch is available in a tagged release.

### Workarounds
_Is there a way for users to fix or remediate the vulnerability without upgrading?_

While upgrading is the most secure and recommended path, users can mitigate the vulnerability using one of the following methods:

#### 1. Use a Validating Interceptor (Recommended Mitigation)
Add an "outermost" interceptor to your server that validates the path before any other authorization logic runs:

```go
func pathValidationInterceptor(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
    if info.FullMethod == "" || info.FullMethod[0] != '/' {
        return nil, status.Errorf(codes.Unimplemented, "malformed method name")
    }   
    return handler(ctx, req)
}

// Ensure this is the FIRST interceptor in your chain
s := grpc.NewServer(
    grpc.ChainUnaryInterceptor(pathValidationInterceptor, authzInterceptor),
)
```

#### 2. Infrastructure-Level Normalization
If your gRPC server is behind a reverse proxy or load balancer (such as Envoy, NGINX, or an L7 Cloud Load Balancer), ensure it is configured to enforce strict HTTP/2 compliance for pseudo-headers and reject or normalize requests where the `:path` header does not start with a leading slash.

#### 3. Policy Hardening
Switch to a "default deny" posture in your authorization policies (explicitly listing all allowed paths and denying everything else) to reduce the risk of bypasses via malformed inputs.

</blockquote>
</details>

<a href="https://scout.docker.com/v/GHSA-hrxh-6v49-42gf?s=github&n=grpc&ns=google.golang.org&t=golang&vr=%3C1.82.1"><img alt="high 8.8: GHSA--hrxh--6v49--42gf" src="https://img.shields.io/badge/GHSA--hrxh--6v49--42gf-lightgrey?label=high%208.8&labelColor=e25d68"/></a> <i>Uncaught Exception</i>

<table>
<tr><td>Affected range</td><td><code><1.82.1</code></td></tr>
<tr><td>Fixed version</td><td><code>1.82.1</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.8</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:H/VA:H/SC:N/SI:N/SA:N</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Multiple security vulnerabilities have been identified and addressed in grpc-go affecting the xDS RBAC authorization engine (internal/xds/rbac) and the HTTP/2 transport server implementation (internal/transport). These vulnerabilities could result in:

- Authorization Bypass (Fail-Open) when translating xDS RBAC policies containing `Metadata` or `RequestedServerName` fields.
- Denial of Service (High CPU Consumption) due to an HTTP/2 Rapid Reset mitigation bypass during client-initiated stream resets.
- Denial of Service (Server Panic) when parsing crafted xDS RBAC policies containing `NOT` rules around unsupported fields.


### Impact
_What kind of vulnerability is it? Who is impacted?_

#### xDS RBAC Authorization Bypass via `Metadata` & `RequestedServerName` matchers

- Affected Component: xDS RBAC 
- Impact: When building policy matchers for gRPC RBAC from xDS configurations, unsupported `permission` and `principal` rules (specifically `Metadata` and `RequestedServerName`) were silently ignored and treated as no-ops.
  - If an authorization policy relied purely on these matchers for access control, treating those rules as no-ops effectively removed the restrictions.
- If these unsupported rules were nested inside logical `NOT` rules (`Permission_NotRule` / `Principal_NotId`) or multi-condition `OR/AND` rules, silently dropping them changed the boolean logic flow of the authorization engine.

As a result, policy evaluation decisions could fail open, allowing unauthorized clients to access protected gRPC services or resources.

#### HTTP/2 Rapid Reset Mitigation Bypass / Denial of Service via Stream Aborts

- Affected Component: HTTP/2 transport
- Impact: Earlier mitigations in grpc-go for HTTP/2 Rapid Reset only applied threshold checks to items that directly resulted in control frames being written back to the wire, such as `SETTINGS` ACKs or server-initiated `RST_STREAM`s.

When a client initiated a rapid flood of stream creation (`HEADERS`) immediately followed by stream termination `RST_STREAM`, items queued up in the control buffer without counting against the transport response frame threshold. An attacker can repeatedly trigger this flood sequence to bypass reader blocking, resulting in high CPU usage, and Denial of Service (DoS).

#### Denial of Service (Panic) in xDS RBAC Engine via Unsupported Fields inside NOT Rules

- Affected Component: xDS RBAC 
- Impact: The xDS RBAC policy translators recursively generate matchers for nested rules. When a `NOT` rule wrapped an unsupported or unhandled field (such as `SourcedMetadata`), the recursive step returned an empty matcher. This could result in a runtime panic when the RBAC engine attempts to authorize an incoming request.

An attacker or misconfigured/malicious xDS management server delivering an LDS/RDS update containing a `NOT` rule around an unhandled field causes the gRPC server process to crash immediately (CWE-248 / Denial of Service).

### Patches
_Has the problem been patched? What versions should users upgrade to?_

All three issues have been fixed in `master` and will be released in 1.82.1 shortly.

### Workarounds
_Is there a way for users to fix or remediate the vulnerability without upgrading?_

If upgrading grpc-go immediately is not possible, apply the following workarounds based on your deployment architecture:

* For xDS RBAC Vulnerabilities & Panics: Ensure that upstream xDS management servers do not push RBAC policies containing `Metadata`, `RequestedServerName`, or `NOT` rules wrapping unsupported fields (such as `SourcedMetadata`) to grpc-go servers.
* For HTTP/2 Rapid Reset DOS: Configure upstream reverse proxies or load balancers (such as Envoy) with strict HTTP/2 `max_concurrent_streams` limits and active rate limiting on `RST_STREAM` frequency per connection.

### Severity

  | Vulnerability | Qualitative Severity | Approximate CVSS v3.1 Score | Primary Impact |
  | :--- | :--- | :--- | :--- |
  | **xDS RBAC Authorization Bypass** | **High** | `8.2` | Unauthorized Access / Fail-Open |
  | **HTTP/2 Rapid Reset DOS Bypass** | **High** | `7.5` | High CPU Consumption / Denial of Service |
  | **xDS RBAC Engine Server Panic** | **Medium** | `5.9` | Process Crash / Denial of Service |

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-84445?s=github&n=grpc&ns=google.golang.org&t=golang&vr=%3C1.82.2"><img alt="high 8.7: CVE--2026--84445" src="https://img.shields.io/badge/CVE--2026--84445-lightgrey?label=high%208.7&labelColor=e25d68"/></a> <i>Improper Validation of Array Index</i>

<table>
<tr><td>Affected range</td><td><code><1.82.2</code></td></tr>
<tr><td>Fixed version</td><td><code>1.82.2</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N/E:X/CR:X/IR:X/AR:X/MAV:X/MAC:X/MAT:X/MPR:X/MUI:X/MVC:X/MVI:X/MVA:X/MSC:X/MSI:X/MSA:X/S:X/AU:X/R:X/V:X/RE:X/U:X</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.641%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>51st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A vulnerability exists in gRPC-Go servers configured with `xds.NewGRPCServer()` where a crafted request missing both `:authority` and `Host` headers can cause a server panic, resulting in a Denial of Service (DoS).

Servers built with `xds.NewGRPCServer` install an xDS routing interceptor on every RPC. This interceptor looks up the request’s `:authority` header to pick a virtual host. The HTTP/2 server transport previously accepted requests that had neither `:authority` nor `Host`. When this happened, the xDS routing interceptor attempted to access the first element of an empty slice of authorities, leading to an index out of bounds panic. Since the per-RPC goroutine does not recover from panics, the entire server process would terminate.

This panic occurs in the interceptor pipeline, meaning the transport credentials handshake (TLS, mTLS, or ALTS) and HTTP/2 connection establishment must complete successfully before the crafted request can reach this logic.
- Insecure/Standard TLS: If the server permits insecure (plaintext) connections or standard credentials (where client certs are not checked), any unauthenticated remote attacker can trigger the crash.
- mTLS / ALTS: If strict transport-level authentication is enforced at the network edge or transport layer (e.g., requiring a valid client certificate), the attacker must possess valid transport credentials to initiate the stream and trigger the panic.

### Impact
An attacker can cause a complete outage of the gRPC server by sending a request missing both `:authority` and `Host` headers, provided they can successfully establish a transport connection.

### Patches
The issue has been addressed in `master` (and backported to `1.84.0`, `1.83.2` and `1.82.2`). The fix updates the HTTP/2 transport layer to reject requests missing both `:authority` and `Host` headers early, maintaining consistency with and other gRPC language implementations.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-84304?s=github&n=grpc&ns=google.golang.org&t=golang&vr=%3C%3D1.83.0"><img alt="high 8.7: CVE--2026--84304" src="https://img.shields.io/badge/CVE--2026--84304-lightgrey?label=high%208.7&labelColor=e25d68"/></a> <i>Uncontrolled Resource Consumption</i>

<table>
<tr><td>Affected range</td><td><code><=1.83.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.83.1</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.609%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>50th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact
An unauthenticated remote attacker can initiate a gRPC stream and purposefully fragment their payload into millions of tiny (e.g., 1-byte) HTTP/2 DATA frames. Even if the total payload volume falls within the configured connection and stream flow-control windows, each independent fragment incurs memory overhead due to internal tracking structures and queue allocation.

Repeated fragmentation massively inflates the heap space consumed by the stream. An attacker multiplexing multiple concurrent streams can exhaust the memory bounds of the runtime, forcing a runtime panic or OutOfMemory condition and leading to a remote Denial of Service (DoS).

### Patches
The change to fix this issue is merged in `master` and a patch release, 1.83.1, has been published that contains this fix.

### Workarounds
This vulnerability is mitigated by implementing receive buffer compaction. Consecutive small data buffers are automatically coalesced into larger buffers from a shared pool once the overhead is perceived to be excessive relative to actual payload data, drastically minimizing per-frame memory overheads.

This behavior is enabled by default. A temporary escape hatch is provided via the environment variable `GRPC_GO_EXPERIMENTAL_ENABLE_RECEIVE_BUFFER_COMPACTION=false` to disable the feature if unforeseen issues arise, but it will be removed in a future release.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>github.com/prometheus/prometheus</strong> <code>0.303.0</code> (golang)</summary>

<small><code>pkg:golang/github.com/prometheus/prometheus@0.303.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-42154?s=github&n=prometheus&ns=github.com%2Fprometheus&t=golang&vr=%3C0.305.2"><img alt="high 7.5: CVE--2026--42154" src="https://img.shields.io/badge/CVE--2026--42154-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Uncontrolled Resource Consumption</i>

<table>
<tr><td>Affected range</td><td><code><0.305.2</code></td></tr>
<tr><td>Fixed version</td><td><code>0.311.3</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.813%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>58th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact

The remote read endpoint (`/api/v1/read`) does not validate the declared decoded length in a snappy-compressed request body before allocating memory.
An unauthenticated attacker can send a small payload that causes a huge heap allocation per request. Under concurrent load this can exhaust available memory and crash the Prometheus process.

### Patches
_Has the problem been patched? What versions should users upgrade to?_

Fixed in 3.11.3 and 3.5.3 LTS. Users should upgrade to these versions or later.

### Workarounds
User who can not upgrade can place Prometheus behind a reverse proxy or firewall that requires authentication before requests reach /api/v1/read.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-42151?s=github&n=prometheus&ns=github.com%2Fprometheus&t=golang&vr=%3E%3D0.45.2%2C%3C0.311.3"><img alt="high 7.5: CVE--2026--42151" src="https://img.shields.io/badge/CVE--2026--42151-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Exposure of Sensitive Information to an Unauthorized Actor</i>

<table>
<tr><td>Affected range</td><td><code>>=0.45.2<br/><0.311.3</code></td></tr>
<tr><td>Fixed version</td><td><code>0.311.3</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.352%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>29th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact

Users who use Azure AD remote write with OAuth authentication are impacted.

The `client_secret` field in the Azure AD remote write OAuth configuration (`storage/remote/azuread`) was typed as `string` instead of `Secret`. Prometheus redacts fields of type `Secret` when serving the configuration via the `/-/config` HTTP API endpoint. Because the field was a plain string, the Azure OAuth client secret was exposed in plaintext to any user or process with access to that endpoint.

### Patches

The problem has been patched by changing `ClientSecret` in `OAuthConfig` to `Secret`. Users should upgrade to 3.11.3 or 3.5.3 LTS.

### Workarounds

Users  who can not upgrade can switch to Managed Identity or Workload Identity authentication for Azure AD remote write, which do not involve a client secret.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>github.com/go-jose/go-jose/v4</strong> <code>4.1.0</code> (golang)</summary>

<small><code>pkg:golang/github.com/go-jose/go-jose/v4@4.1.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-34986?s=github&n=v4&ns=github.com%2Fgo-jose%2Fgo-jose&t=golang&vr=%3C4.1.4"><img alt="high 7.5: CVE--2026--34986" src="https://img.shields.io/badge/CVE--2026--34986-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Uncaught Exception</i>

<table>
<tr><td>Affected range</td><td><code><4.1.4</code></td></tr>
<tr><td>Fixed version</td><td><code>4.1.4</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.663%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>52nd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact

Decrypting a JSON Web Encryption (JWE) object will panic if the `alg` field indicates a key wrapping algorithm ([one ending in `KW`](https://pkg.go.dev/github.com/go-jose/go-jose/v4#pkg-constants), with the exception of `A128GCMKW`, `A192GCMKW`, and `A256GCMKW`) and the `encrypted_key` field is empty. The panic happens when `cipher.KeyUnwrap()` in `key_wrap.go` attempts to allocate a slice with a zero or negative length based on the length of the `encrypted_key`.

This code path is reachable from `ParseEncrypted()` / `ParseEncryptedJSON()` / `ParseEncryptedCompact()` followed by `Decrypt()` on the resulting object. Note that the parse functions take a list of accepted key algorithms. If the accepted key algorithms do not include any key wrapping algorithms, parsing will fail and the application will be unaffected.

This panic is also reachable by calling `cipher.KeyUnwrap()` directly with any `ciphertext` parameter less than 16 bytes long, but calling this function directly is less common.

Panics can lead to denial of service.

### Fixed In

4.1.4 and v3.0.5

### Workarounds

If the list of `keyAlgorithms` passed to `ParseEncrypted()` / `ParseEncryptedJSON()` / `ParseEncryptedCompact()` does not include key wrapping algorithms (those ending in `KW`), your application is unaffected.

If your application uses key wrapping, you can prevalidate to the JWE objects to ensure the `encrypted_key` field is nonempty. If your application accepts JWE Compact Serialization, apply that validation to the corresponding field of that serialization (the data between the first and second `.`).

### Thanks

Thanks to Datadog's Security team for finding this issue.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-116587?s=github&n=v4&ns=github.com%2Fgo-jose%2Fgo-jose&t=golang&vr=%3C%3D4.1.5"><img alt="high 7.5: CVE--2026--116587" src="https://img.shields.io/badge/CVE--2026--116587-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Inefficient Algorithmic Complexity</i>

<table>
<tr><td>Affected range</td><td><code><=4.1.5</code></td></tr>
<tr><td>Fixed version</td><td><code>4.1.6</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.489%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>43rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Summary

A crafted RSA key inside a JWK can cause operations that parse JWKs to consume excess CPU.

### Details

go-jose does not check for bounds on RSA modulus and primes before validating them. Values are passed directly to `crypto/rsa.PrivateKey.Validate()`. On Go 1.24+, this takes cubic time complexity with respect to the RSA modulus and primes. This allows an attacker to supply a crafted JWK to consume excessive CPU.

https://github.com/go-jose/go-jose/blob/5b371aecfcf7aabe06068d67da4344591ecddc76/jwk.go#L655-L700

### Proof of concept

No special configuration of go-jose is required to reproduce this vulnerability.

```go
package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"time"

	"github.com/go-jose/go-jose/v4"
)

func main() {
	// The RSA parameters can be complete junk. The CPU cost is in validating them.
	primeBits := 16384
	p := new(big.Int).Lsh(big.NewInt(1), uint(primeBits-1))
	p.SetBit(p, 0, 1)
	n := new(big.Int).Lsh(big.NewInt(1), 2048)
	e := big.NewInt(65537)
	d := big.NewInt(3)
	q := big.NewInt(3)

	jwk := map[string]string{
		"kty": "RSA",
		"n":   base64.RawURLEncoding.EncodeToString(n.Bytes()),
		"e":   base64.RawURLEncoding.EncodeToString(e.Bytes()),
		"d":   base64.RawURLEncoding.EncodeToString(d.Bytes()),
		"p":   base64.RawURLEncoding.EncodeToString(p.Bytes()),
		"q":   base64.RawURLEncoding.EncodeToString(q.Bytes()),
	}

	protected := map[string]any{
		"alg": "RS256",
		"jwk": jwk,
	}
	protJSON, _ := json.Marshal(protected)

	jws := map[string]string{
		"protected": base64.RawURLEncoding.EncodeToString(protJSON),
		"payload":   base64.RawURLEncoding.EncodeToString([]byte(`{}`)),
		"signature": base64.RawURLEncoding.EncodeToString([]byte("not-a-real-signature")),
	}
	jwsJSON, _ := json.Marshal(jws)

	start := time.Now()
	_, err := jose.ParseSigned(string(jwsJSON), []jose.SignatureAlgorithm{jose.RS256})
	elapsed := time.Since(start)

	fmt.Printf("prime bits: %d\n", primeBits)
	fmt.Printf("parse time: %s\n", elapsed)
	fmt.Printf("parse error: %v\n", err)
}
```

### Impact

Denial of service vulnerability. Any application that uses go-jose to parse JWKs from untrusted sources is affected and should patch immediately.

### Credits

Reported by Yuval Saggie and Mor Weinberger (powered by Echo Frontier)

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>github.com/apache/thrift</strong> <code>0.21.0</code> (golang)</summary>

<small><code>pkg:golang/github.com/apache/thrift@0.21.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-43871?s=github&n=thrift&ns=github.com%2Fapache&t=golang&vr=%3C0.24.0"><img alt="high 8.7: CVE--2026--43871" src="https://img.shields.io/badge/CVE--2026--43871-lightgrey?label=high%208.7&labelColor=e25d68"/></a> <i>Loop with Unreachable Exit Condition ('Infinite Loop')</i>

<table>
<tr><td>Affected range</td><td><code><0.24.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.24.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>8.7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.030%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>64th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Loop with Unreachable Exit Condition ('Infinite Loop') vulnerability in Apache Thrift Python, Go, PHP and Java bindings.This issue affects Apache Thrift: before 0.24.0.

Users are recommended to upgrade to version 0.24.0, which fixes the issue.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-41602?s=github&n=thrift&ns=github.com%2Fapache&t=golang&vr=%3C0.23.0"><img alt="high 7.5: CVE--2026--41602" src="https://img.shields.io/badge/CVE--2026--41602-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Integer Overflow or Wraparound</i>

<table>
<tr><td>Affected range</td><td><code><0.23.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.23.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>1.163%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>68th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Integer Overflow or Wraparound vulnerability in Apache Thrift TFramedTransport Go language implementation

This issue affects Apache Thrift: before 0.23.0.

Users are recommended to upgrade to version 0.23.0, which fixes the issue.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>github.com/klauspost/compress</strong> <code>1.18.0</code> (golang)</summary>

<small><code>pkg:golang/github.com/klauspost/compress@1.18.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-116591?s=golang&n=compress&ns=github.com%2Fklauspost&t=golang&vr=%3C1.20.2"><img alt="high : CVE--2026--116591" src="https://img.shields.io/badge/CVE--2026--116591-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><1.20.2</code></td></tr>
<tr><td>Fixed version</td><td><code>1.20.2</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.333%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>27th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

Panic on two-block frames in github.com/klauspost/compress

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-63209?s=github&n=compress&ns=github.com%2Fklauspost&t=golang&vr=%3C%3D1.18.6"><img alt="high 7.5: CVE--2026--63209" src="https://img.shields.io/badge/CVE--2026--63209-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Integer Overflow or Wraparound</i>

<table>
<tr><td>Affected range</td><td><code><=1.18.6</code></td></tr>
<tr><td>Fixed version</td><td><code>1.18.7</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.572%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>48th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

# Signed Integer Overflow in s2.NewDict

## Summary

A signed integer overflow vulnerability in `s2.NewDict()` allows an attacker to bypass repeat index validation by supplying a dictionary with a uvarint-encoded repeat value exceeding `MaxInt64`. When `Dict.Encode()` is subsequently called, the overflowed negative repeat value causes an out-of-bounds memory access via `unsafe.Pointer` arithmetic, crashing the process with SIGSEGV.

## Package

- **Name:** `github.com/klauspost/compress/s2`
- **Ecosystem:** Go
- **Affected versions:** <= v1.18.6 (all versions with `NewDict` function)

## Severity

**High (7.5)** — CVSS v3.1: `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`

## Vulnerability

### Type
- CWE-190: Integer Overflow or Wraparound
- CWE-787: Out-of-bounds Write (via unsafe.Pointer)

### Description

The `NewDict()` function reads a uvarint from dictionary data and converts it to `int`:

```go
r, n := binary.Uvarint(dict)
// ...
d.repeat = int(r)
if d.repeat > len(dict) {
    return nil
}
```

When `r` exceeds `MaxInt64` (9223372036854775807), `int(r)` overflows to a negative value. Since a negative number is never greater than a positive length, the validation check is bypassed.

When `Dict.Encode()` is called, the negative `repeat` value causes an integer overflow in `encodeBlockDictGo()`:

```go
repeat := len(dict.dict) - dict.repeat  // overflows: 62 - (-5758978476775341977) = huge positive
candidate := len(dict.dict) - repeat + s // underflows to negative
load32(dict.dict, candidate)             // OOB via unsafe.Pointer
```

`load32` calls `le.Load32` which uses `unsafe.Pointer` arithmetic without bounds checking:

```go
func Load32[I Indexer](b []byte, i I) uint32 {
    return *(*uint32)(unsafe.Add(unsafe.Pointer(unsafe.SliceData(b)), i))
}
```

This causes a segmentation fault (SIGSEGV) when the negative index is dereferenced.

## PoC

```go
package main

import (
    "encoding/binary"
    "fmt"
    "github.com/klauspost/compress/s2"
)

func main() {
    var dictData []byte
    buf := make([]byte, binary.MaxVarintLen64)
    n := binary.PutUvarint(buf, 12687765596934209639) // > MaxInt64
    dictData = append(dictData, buf[:n]...)
    dictData = append(dictData, make([]byte, 16)...) // minimum dict size

    dict := s2.NewDict(dictData)
    // dict is non-nil despite invalid repeat value (overflow bypassed validation)

    src := make([]byte, 64)
    for i := range src { src[i] = byte(i) }
    dict.Encode(nil, src) // SIGSEGV: OOB access via unsafe.Pointer
}
```

## Impact

- **Denial of Service:** The process crashes immediately with SIGSEGV

## Attack Vector

Any application that:
1. Accepts user-supplied S2 dictionary data via `s2.NewDict()`
2. Calls `Dict.Encode()` on any data ≥32 bytes

## Suggested Fix

Validate the uvarint value before converting to int:

```go
if r > math.MaxInt64 {
    return nil
}
d.repeat = int(r)
```

Or use `uint` for the repeat field and validate against `uint(len(dict))`.

## References

- Source: `s2/dict.go` lines 59-61 (vulnerability), `s2/encode_all.go` line 947 (crash site)
- Commit: 539243b (v1.18.6 + 4 commits)

## Credits
Christopher Linke / https://github.com/celinke97/

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>glibc</strong> <code>2.34-290.el9_9</code> (rpm)</summary>

<small><code>pkg:rpm/redhat/glibc@2.34-290.el9_9?os_name=redhatlinux&os_version=9</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-0861?s=redhat&n=glibc&ns=redhat&t=rpm&osn=redhatlinux&osv=9&vr=%3E%3D0"><img alt="high 9.8: CVE--2026--0861" src="https://img.shields.io/badge/CVE--2026--0861-lightgrey?label=high%209.8&labelColor=e25d68"/></a> <i>Integer Overflow or Wraparound</i>

<table>
<tr><td>Affected range</td><td><code>>=0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>CVSS Score</td><td><code>9.8</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.386%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>33rd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A flaw was found in the glibc library. Passing an excessively large alignment value to the memalign suite of functions, such as memalign, posix_memalign, aligned_alloc, valloc and pvalloc, an integer overflow can occur during internal size calculations due to improper overflow checks, causing an allocation of a small chunk of memory which is subsequently used for writing. This issue can result in an application crash or heap memory corruption.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-4046?s=redhat&n=glibc&ns=redhat&t=rpm&osn=redhatlinux&osv=9&vr=%3E%3D0"><img alt="high 7.5: CVE--2026--4046" src="https://img.shields.io/badge/CVE--2026--4046-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Reachable Assertion</i>

<table>
<tr><td>Affected range</td><td><code>>=0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.389%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>34th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A flaw was found in glibc, the GNU C Library. A remote attacker could exploit this vulnerability by providing specially crafted inputs using the IBM1390 or IBM1399 character sets to the `iconv()` function. This could lead to an assertion failure, causing the application to crash and resulting in a Denial of Service (DoS).

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>go.opentelemetry.io/otel/sdk</strong> <code>1.35.0</code> (golang)</summary>

<small><code>pkg:golang/go.opentelemetry.io/otel/sdk@1.35.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-39883?s=github&n=sdk&ns=go.opentelemetry.io%2Fotel&t=golang&vr=%3E%3D1.15.0%2C%3C%3D1.42.0"><img alt="high 7.3: CVE--2026--39883" src="https://img.shields.io/badge/CVE--2026--39883-lightgrey?label=high%207.3&labelColor=e25d68"/></a> <i>Untrusted Search Path</i>

<table>
<tr><td>Affected range</td><td><code>>=1.15.0<br/><=1.42.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.43.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.3</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:4.0/AV:L/AC:H/AT:N/PR:L/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.262%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>18th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

## Summary

The fix for GHSA-9h8m-3fm2-qjrq (CVE-2026-24051) changed the Darwin `ioreg` command to use an absolute path but left the BSD `kenv` command using a bare name, allowing the same PATH hijacking attack on BSD and Solaris platforms.

## Root Cause

`sdk/resource/host_id.go` line 42:

    if result, err := r.execCommand("kenv", "-q", "smbios.system.uuid"); err == nil {

Compare with the fixed Darwin path at line 58:

    result, err := r.execCommand("/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice")

The `execCommand` helper at `sdk/resource/host_id_exec.go` uses `exec.Command(name, arg...)` which searches `$PATH` when the command name contains no path separator.

Affected platforms (per build tag in `host_id_bsd.go:4`): DragonFly BSD, FreeBSD, NetBSD, OpenBSD, Solaris.

The `kenv` path is reached when `/etc/hostid` does not exist (line 38-40), which is common on FreeBSD systems.

## Attack

1. Attacker has local access to a system running a Go application that imports `go.opentelemetry.io/otel/sdk`
2. Attacker places a malicious `kenv` binary earlier in `$PATH`
3. Application initializes OpenTelemetry resource detection at startup
4. `hostIDReaderBSD.read()` calls `exec.Command("kenv", ...)` which resolves to the malicious binary
5. Arbitrary code executes in the context of the application

Same attack vector and impact as CVE-2026-24051.

## Suggested Fix

Use the absolute path:

    if result, err := r.execCommand("/bin/kenv", "-q", "smbios.system.uuid"); err == nil {

On FreeBSD, `kenv` is located at `/bin/kenv`.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-24051?s=github&n=sdk&ns=go.opentelemetry.io%2Fotel&t=golang&vr=%3E%3D1.21.0%2C%3C1.40.0"><img alt="high 7.0: CVE--2026--24051" src="https://img.shields.io/badge/CVE--2026--24051-lightgrey?label=high%207.0&labelColor=e25d68"/></a> <i>Untrusted Search Path</i>

<table>
<tr><td>Affected range</td><td><code>>=1.21.0<br/><1.40.0</code></td></tr>
<tr><td>Fixed version</td><td><code>1.40.0</code></td></tr>
<tr><td>CVSS Score</td><td><code>7</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.176%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>7th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

### Impact
The OpenTelemetry Go SDK in version `v1.20.0`-`1.39.0` is vulnerable to Path Hijacking (Untrusted Search Paths) on macOS/Darwin systems. The resource detection code in `sdk/resource/host_id.go` executes the `ioreg` system command using a search path. An attacker with the ability to locally modify the PATH environment variable can achieve Arbitrary Code Execution (ACE) within the context of the application.

### Patches
This has been patched in [d45961b](https://github.com/open-telemetry/opentelemetry-go/commit/d45961bcda453fcbdb6469c22d6e88a1f9970a53), which was released with `v1.40.0`.

### References
- [CWE-426: Untrusted Search Path](https://cwe.mitre.org/data/definitions/426.html)

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>pcre2</strong> <code>10.40-7.el9_8</code> (rpm)</summary>

<small><code>pkg:rpm/redhat/pcre2@10.40-7.el9_8?os_name=redhatlinux&os_version=9</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-103111?s=redhat&n=pcre2&ns=redhat&t=rpm&osn=redhatlinux&osv=9&vr=%3E%3D0"><img alt="high 7.6: CVE--2026--103111" src="https://img.shields.io/badge/CVE--2026--103111-lightgrey?label=high%207.6&labelColor=e25d68"/></a> <i>Out-of-bounds Write</i>

<table>
<tr><td>Affected range</td><td><code>>=0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>CVSS Score</td><td><code>7.6</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:H/A:L</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.269%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>19th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A flaw was found in pcre2. When an application processes attacker-controlled regular expressions using certain Just-In-Time (JIT) compiler interfaces, an out-of-bounds write with arbitrary data can occur. An attacker could exploit this vulnerability to achieve arbitrary code execution, corrupt memory, or cause a denial of service (DoS).

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-89161?s=redhat&n=pcre2&ns=redhat&t=rpm&osn=redhatlinux&osv=9&vr=%3E%3D0"><img alt="high 7.4: CVE--2026--89161" src="https://img.shields.io/badge/CVE--2026--89161-lightgrey?label=high%207.4&labelColor=e25d68"/></a> <i>Multiple Releases of Same Resource or Handle</i>

<table>
<tr><td>Affected range</td><td><code>>=0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>CVSS Score</td><td><code>7.4</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:L/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.126%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>2nd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A flaw was found in PCRE2, a library for processing regular expressions. The `pcre2_jit_match` function, which handles just-in-time (JIT) compilation for regular expressions, incorrectly manages memory when processing certain inputs. This memory corruption vulnerability could allow a local attacker to cause the application to crash, leading to a denial of service, or potentially execute unauthorized code.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 2" src="https://img.shields.io/badge/H-2-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>golang.org/x/text</strong> <code>0.24.0</code> (golang)</summary>

<small><code>pkg:golang/golang.org/x/text@0.24.0</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-56852?s=golang&n=text&ns=golang.org%2Fx&t=golang&vr=%3C0.39.0"><img alt="high : CVE--2026--56852" src="https://img.shields.io/badge/CVE--2026--56852-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.39.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.39.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.475%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>42nd percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A norm.Iter can enter an infinite loop when handling input containing invalid UTF-8 bytes.

</blockquote>
</details>

<a href="https://scout.docker.com/v/CVE-2026-56851?s=golang&n=text&ns=golang.org%2Fx&t=golang&vr=%3C0.41.0"><img alt="high : CVE--2026--56851" src="https://img.shields.io/badge/CVE--2026--56851-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><0.41.0</code></td></tr>
<tr><td>Fixed version</td><td><code>0.41.0</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.466%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>41st percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The Nickname profile can panic with an out-of-bounds slice error when transforming crafted input into a short destination buffer.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 1" src="https://img.shields.io/badge/H-1-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>attr</strong> <code>2.6.0-2.el9</code> (rpm)</summary>

<small><code>pkg:rpm/redhat/attr@2.6.0-2.el9?os_name=redhatlinux&os_version=9</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-54371?s=redhat&n=attr&ns=redhat&t=rpm&osn=redhatlinux&osv=9&vr=%3E%3D0"><img alt="high 7.1: CVE--2026--54371" src="https://img.shields.io/badge/CVE--2026--54371-lightgrey?label=high%207.1&labelColor=e25d68"/></a> <i>Improper Link Resolution Before File Access ('Link Following')</i>

<table>
<tr><td>Affected range</td><td><code>>=0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>CVSS Score</td><td><code>7.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.146%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>4th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A flaw was found in the `attr` component, specifically within the `getfattr` utility. This vulnerability allows a local attacker to perform a symlink traversal attack. By replacing a pathname component with a symbolic link during directory hierarchy traversal, an attacker can redirect `getfattr` operations to arbitrary files. This can lead to local privilege escalation when `getfattr` is executed by a privileged process over a path controlled by the attacker.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 1" src="https://img.shields.io/badge/H-1-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>acl</strong> <code>2.4.0-2.el9</code> (rpm)</summary>

<small><code>pkg:rpm/redhat/acl@2.4.0-2.el9?os_name=redhatlinux&os_version=9</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-54369?s=redhat&n=acl&ns=redhat&t=rpm&osn=redhatlinux&osv=9&vr=%3E%3D0"><img alt="high 7.1: CVE--2026--54369" src="https://img.shields.io/badge/CVE--2026--54369-lightgrey?label=high%207.1&labelColor=e25d68"/></a> <i>Improper Link Resolution Before File Access ('Link Following')</i>

<table>
<tr><td>Affected range</td><td><code>>=0</code></td></tr>
<tr><td>Fixed version</td><td><strong>Not Fixed</strong></td></tr>
<tr><td>CVSS Score</td><td><code>7.1</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.153%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>5th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

A flaw was found in the `acl` component, specifically within its `libacl` pathname-based functions. A local attacker could exploit this vulnerability by using a symbolic link to replace a pathname component. This could allow the attacker to redirect access control list (ACL) read or write operations to arbitrary files or directories, leading to unauthorized manipulation of ACLs and ultimately local privilege escalation.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 1" src="https://img.shields.io/badge/H-1-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>go.etcd.io/etcd/client/pkg/v3</strong> <code>3.5.21</code> (golang)</summary>

<small><code>pkg:golang/go.etcd.io/etcd/client/pkg/v3@3.5.21</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-73500?s=golang&n=v3&ns=go.etcd.io%2Fetcd%2Fclient%2Fpkg&t=golang&vr=%3C3.5.33"><img alt="high : CVE--2026--73500" src="https://img.shields.io/badge/CVE--2026--73500-lightgrey?label=high%20&labelColor=e25d68"/></a> 

<table>
<tr><td>Affected range</td><td><code><3.5.33</code></td></tr>
<tr><td>Fixed version</td><td><code>3.5.33</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.396%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>34th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

In go.etcd.io/etcd/client/pkg/v3 before 3.5.33, 3.6.14, and 3.7.1, TLS handshakes on listeners created by NewTLSListener do not enforce a handshake deadline. An unauthenticated network attacker who connects to an etcd TLS listener without sending a ClientHello causes a goroutine and a tracking map entry to block indefinitely. Opening many such connections exhausts memory, leading to a denial of service.

</blockquote>
</details>
</details></td></tr>

<tr><td valign="top">
<details><summary><img alt="critical: 0" src="https://img.shields.io/badge/C-0-lightgrey"/> <img alt="high: 1" src="https://img.shields.io/badge/H-1-e25d68"/> <img alt="medium: 0" src="https://img.shields.io/badge/M-0-lightgrey"/> <img alt="low: 0" src="https://img.shields.io/badge/L-0-lightgrey"/> <!-- unspecified: 0 --><strong>github.com/buger/jsonparser</strong> <code>1.1.1</code> (golang)</summary>

<small><code>pkg:golang/github.com/buger/jsonparser@1.1.1</code></small><br/>
<a href="https://scout.docker.com/v/CVE-2026-32285?s=github&n=jsonparser&ns=github.com%2Fbuger&t=golang&vr=%3C%3D1.1.1"><img alt="high 7.5: CVE--2026--32285" src="https://img.shields.io/badge/CVE--2026--32285-lightgrey?label=high%207.5&labelColor=e25d68"/></a> <i>Out-of-bounds Read</i>

<table>
<tr><td>Affected range</td><td><code><=1.1.1</code></td></tr>
<tr><td>Fixed version</td><td><code>1.1.2</code></td></tr>
<tr><td>CVSS Score</td><td><code>7.5</code></td></tr>
<tr><td>CVSS Vector</td><td><code>CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H</code></td></tr>
<tr><td>EPSS Score</td><td><code>0.797%</code></td></tr>
<tr><td>EPSS Percentile</td><td><code>57th percentile</code></td></tr>
</table>

<details><summary>Description</summary>
<blockquote>

The Delete function fails to properly validate offsets when processing malformed JSON input. This can lead to a negative slice index and a runtime panic, allowing a denial of service attack.

</blockquote>
</details>
</details></td></tr>
</table>

