// SPDX-License-Identifier: Apache-2.0
const MONACO_ROOT = "https://cdn.jsdelivr.net/npm/monaco-editor@0.55.1/min/vs";
const DOCUMENT_URI = "untitled:playground.vela";
const $ = (id) => document.getElementById(id);
const examples = {
    squares: {
        expression: "Square(7)", valueType: "Nat",
        source: `module Playground;

/// A small function with a mathematical result.
public const Nat Square(Nat value) => value * value;

/// A named value, computed during compilation.
public const Nat StartingPoint = 7;

/// Combine earlier functions with an immutable local.
public Nat SumOfSquares(Nat left, Nat right)
{
    let total = Square(left) + Square(right);
    return total;
}

/// Try this expression in the console, too.
public Nat Main() => SumOfSquares(3, 4);
`,
    },
    branches: {
        expression: "WithinLimit(8)", valueType: "bool",
        source: `module Decisions;

/// The upper bound is an ordinary mathematical natural.
public const Nat Limit = 10;

/// Every branch returns a result of the declared type.
public bool WithinLimit(Nat value)
{
    if (value <= Limit)
    {
        return true;
    }
    else
    {
        return false;
    }
}

/// Natural-number comparison produces a boolean.
public bool SameSquare(Nat left, Nat right)
{
    let leftSquare = left * left;
    let rightSquare = right * right;
    return leftSquare == rightSquare;
}
`,
    },
    logic: {
        expression: "CanProceed(value: 8, paused: false)", valueType: "bool",
        source: `module Logic;

/// Boolean operators combine comparisons, checking the lower bound first.
public bool InRange(Nat value) => value >= 3 && value < 10;

/// Negation and disjunction describe the ordinary Boolean decision.
public bool CanProceed(Nat value, bool paused) => !paused && (InRange(value) || value == 20);

/// Inequality works on both naturals and booleans.
public bool Changed(Nat before, Nat after, bool previous, bool current)
{
    return before != after || previous != current;
}

/// Try CanProceed(2, false), CanProceed(20, false), and CanProceed(8, true).
public bool Main() => CanProceed(value: 8, paused: false);
`,
    },
    subtraction: {
        expression: "Remaining(total: 5, used: 8)", valueType: "Nat",
        source: `module NaturalArithmetic;

/// Natural subtraction stops at zero: Remaining(5, 8) is zero.
public Nat Remaining(Nat total, Nat used) => total - used;

/// Multiplication binds tighter; addition and subtraction group left to right.
public Nat Adjusted(Nat value) => value * 3 + 2 - 4;

/// Ordering can decide whether any mathematical capacity remains.
public bool HasRoom(Nat total, Nat used) => total > used;

/// Try Remaining(12, 5), Adjusted(4), and HasRoom(5, 8) in the console.
public Nat Main() => Remaining(total: 12, used: 5);
`,
    },
    division: {
        expression: "Groups(count: 17, size: 5)", valueType: "Nat",
        source: `module Grouping;

/// Divide a quantity into complete groups: Groups(17, 5) is 3.
public Nat Groups(Nat count, Nat size) => count / size;

/// Keep the amount left over: Leftover(17, 5) is 2.
public Nat Leftover(Nat count, Nat size) => count % size;

/// Multiplication, division and remainder group from left to right.
/// Regroup(20, 3) is 12; 20 / (3 * 2) is 3.
public Nat Regroup(Nat count, Nat size) => count / size * 2;

/// Mathematical Nat operations are total: 17 / 0 is 0; 17 % 0 is 17.
public const Nat ZeroGroups = Groups(17, 0);
public const Nat Unchanged = Leftover(17, 0);

/// Try Leftover(17, 5), Regroup(20, 3), ZeroGroups, and Unchanged.
public Nat Main() => Groups(count: 17, size: 5);
`,
    },
    constants: {
        expression: "Process(5)", valueType: "Nat",
        source: `module Configuration;

/// Available to both static evaluation and ordinary calls.
public const Nat Square(Nat value) => value * value;

/// The configuration is fixed before runtime data arrives.
public const Nat Gain = 4;

/// A static parameter can initialize a required constant.
public Nat Scale(const Nat gain, Nat sample)
{
    const Nat multiplier = Square(gain);
    return multiplier * sample;
}

/// Apply the configured multiplier to a sample.
public Nat Process(Nat sample) => Scale(gain: Gain, sample: sample);
`,
    },
    bindings: {
        expression: "Count(true)", valueType: "Nat",
        source: `module Bindings;

/// Immutable locals may carry explicit type annotations.
/// Check style to inspect optional advisory findings.
public Nat Count(bool selected)
{
    let Nat count = 1_000;
    let bool ready = selected == true;
    if (ready)
    {
        return count;
    }
    else
    {
        return 0;
    }
}
`,
    },
    named: {
        expression: "Total()", valueType: "Nat",
        source: `module NamedArguments;

/// Decimal natural literals accept separators for readability.
public const Nat Base = 1_000;

/// Parameter names document each value at a call site.
public Nat Combine(Nat left, Nat right) => left + right;

/// Named arguments and documented functions share ordinary compiler facts.
public Nat Total()
{
    let Nat amount = Combine(left: Base, right: 8);
    return amount + 16;
}
`,
    },
    generic: {
        label: "Generics & higher-order functions",
        expression: "HigherOrder()", valueType: "Nat",
        source: `module GenericFunctions;

/// TValue is inferred separately at every call.
public definition TValue Identity<TValue>(TValue value) => value;

/// Functions are values, with their own input and result types.
public definition TResult Apply<TInput, TResult>(Fn(TInput value) -> TResult function, TInput value) =>
    function(value: value);

public definition (Nat, bool) DifferentTypes() =>
    (Identity(7), Identity(true));

/// Evaluate HigherOrder(): the expected result is 42.
public definition Nat HigherOrder() =>
    Apply(function: value => value + 1, value: 41);

/// Proof blocks verify their declared equality proposition.
public lemma Result()
    ensures HigherOrder() == 42
    proof
    {
        assert HigherOrder() == 42;
    }
`,
    },
    vectors: {
        label: "Indexed vectors & safe lookup",
        expression: "Second()", valueType: "Nat",
        source: `module SafeLookup;

/// The length is part of the vector's type.
public definition Vec<Nat, 3> Samples() =>
    VCons(10, VCons(20, VCons(30, VNil<Nat>())));

/// Fin<3> describes exactly the three valid indices.
public definition Nat Read(Fin<3> index) => At(Samples(), index);

/// The successor of zero selects the second value: 20.
public definition Nat Second() => Read(FSucc(FZero<1>()));

public lemma SelectedValue()
    ensures Second() == 20
    proof
    {
        assert Second() == 20;
    }

// Try Read(FZero<2>()) and Read(FSucc(FSucc(FZero<0>()))).
// Read(FZero<3>()) is rejected: Fin<4> cannot index a Vec<Nat, 3>.
`,
    },
    dependent: {
        label: "Dependent functions & length proofs",
        expression: "PreservedValue()", valueType: "Nat",
        source: `module LengthPreservation;

/// The same inferred length appears in both the input and result.
/// TElement names a type; length is a natural-number value index.
public definition Vec<TElement, length> Copy<TElement, ghost Nat length>(Vec<TElement, length> values) => values;

/// Later parameter types can depend on an earlier value parameter.
public definition Fn(Nat length, Vec<Nat, length> values) -> Vec<Nat, length> Preserve() =>
    (Nat length, Vec<Nat, length> values) => values;

public definition Vec<Nat, 1> Original() => VCons(42, VNil<Nat>());

public definition Vec<Nat, 1> Preserved() =>
    Preserve()(length: 1, values: Copy(Original()));

public definition Nat PreservedValue() => At(Preserved(), FZero<0>());

/// The proposed proof is checked by the elaborator; kernel replay is separate.
public lemma SameValue()
    ensures PreservedValue() == 42
    proof
    {
        assert PreservedValue() == 42;
    }

// Change length: 1 to length: 2 above to see a length mismatch.
// Change 42 to 41 in SameValue to see a false assertion refused.
`,
    },
    formatting: {
        label: "Raw strings & checked formatting",
        expression: "Written(FormatPacket(42, true))", valueType: "Nat",
        source: `module CheckedFormatting;

/// Multi-quote raw string literals need no backslash escapes and dedent by closing quotes.
public definition Vec<Nat, 10> HeaderTag() =>
    """
    [vela-hdr]
    """;

public const Nat HeaderBytes = ByteLength(HeaderTag());

/// Format.Write targets an explicit ref TextBuilder<capacity> without heap allocation.
public TextBuilder<36> FormatPacket(Nat id, bool ok)
{
    let TextBuilder<36> builder = EmptyBuilder();
    let TextBuilder<36> withHeader = Format.Write(ref builder, $"hdr={HeaderTag()} ");
    let TextBuilder<36> complete = Format.Write(ref withHeader, $"id=0x{id:x4} ok={ok}");
    return complete;
}

/// A buffer whose capacity is too small fails closed without partial mutation.
public TextBuilder<12> OverflowPacket(Nat id)
{
    let TextBuilder<12> tiny = EmptyBuilder();
    return Format.Write(ref tiny, $"hdr={HeaderTag()} id=0x{id:x4}");
}

public lemma DedentedHeaderLength()
    ensures HeaderBytes == 10
    proof
    {
        assert HeaderBytes == 10;
    }

public theorem PacketFitsForEveryId()
    ensures forall (Nat id) => Fits(FormatPacket(id, true)) == true
    proof
    {
        assert Fits(FormatPacket(id, true));
    }

public lemma PacketWrites32Bytes()
    ensures Written(FormatPacket(42, true)) == 32
    proof
    {
        assert Written(FormatPacket(42, true)) == 32;
    }

public lemma SmallBufferFailsClosed()
    ensures Fits(OverflowPacket(42)) == false
    proof
    {
        assert Fits(OverflowPacket(42)) == false;
    }

// Try HeaderBytes, Fits(FormatPacket(42, true)), and Fits(OverflowPacket(42)).
// Standalone $"..." without Format.Write(ref builder, ...) is rejected.
`,
    },
    ergonomics: {
        label: "Records, properties, updates & guards",
        expression: "StepIfPositive(2, Counter(Value: 10, Limit: 5))", valueType: "Nat",
        source: `module Ergonomics;

/// Records declare primary-constructor fields and total, read-only expression properties.
public record Counter(Nat Value, Nat Limit)
{
    public bool AtLimit => this.Value >= this.Limit;
    public Nat Remaining => this.Limit - this.Value;
}

/// Top-level expression properties are pure, parameterless computed reads.
public Nat DefaultStep => 1;

/// Expression-form if/else and record update (with { ... }) compose in => bodies.
public definition Counter Advance(Counter counter, Nat step) =>
    if (counter.AtLimit) counter
    else counter with { Value = counter.Value + step };

/// Constructor patterns accept optional declaration-order field labels.
public definition Nat Unpack(Counter counter) =>
    match (counter) {
        Counter(Value: current, Limit: maximum) =>
            if (current <= maximum) maximum - current else 0,
    };

/// Scoped early-exit extraction (let ... else) and flow-refined if (x is Pattern).
public Nat StepIfPositive(Nat value, Counter counter)
{
    let Succ(previous) = value else
    {
        return counter.Value;
    }
    let Counter(Value: base, Limit: limit) = counter;
    return if (previous is Succ(inner)) base + inner + limit else base + limit;
}

public lemma AdvanceStep()
    ensures Advance(Counter(Value: 2, Limit: 5), DefaultStep).Value == 3
    proof
    {
        assert Advance(Counter(Value: 2, Limit: 5), DefaultStep).Value == 3;
    }

public lemma PropertyMatchesUnpack()
    ensures Unpack(Counter(Value: 2, Limit: 5)) == Counter(Value: 2, Limit: 5).Remaining
    proof
    {
        assert Unpack(Counter(Value: 2, Limit: 5)) == Counter(Value: 2, Limit: 5).Remaining;
    }

public lemma GuardAndBranchRefinement()
    ensures StepIfPositive(2, Counter(Value: 10, Limit: 5)) == 15
    proof
    {
        assert StepIfPositive(2, Counter(Value: 10, Limit: 5)) == 15;
    }

// Try Advance(Counter(Value: 2, Limit: 5), DefaultStep).Remaining and Unpack(Counter(Value: 2, Limit: 5)).
`,
    },
};

const state = {
    text: examples.squares.source, version: 1, model: null, editor: null,
    session: null, connected: false, generation: 0, opened: false, syncedVersion: 0,
    capabilities: {}, connection: null, queue: Promise.resolve(), requestId: 0,
    compileTicket: 0, evaluateTicket: 0, checkTimer: null, gallina: "",
    authoringTicket: 0, authoring: null, outlineTicket: 0, inspectTicket: 0,
    outlineSnapshot: null, undoSource: null, inspectPending: false, inspectSelection: "",
    editorServices: null, analysisTicket: 0,
};

let token = new URLSearchParams(location.hash.slice(1)).get("token") || "";
try {
    if (token) sessionStorage.setItem("vela-playground-token", token);
    else token = sessionStorage.getItem("vela-playground-token") || "";
} catch { /* A tab with storage disabled can still use its launch fragment. */ }
if (location.hash) history.replaceState(null, "", location.pathname + location.search);

$("source-fallback").value = state.text;

function status(message, failed = false) {
    $("connection-label").textContent = message;
    $("connection-dot").className = `status-dot${failed ? " failed" : state.connected ? " connected" : ""}`;
    $("reconnect-button").hidden = !failed || !token;
}

function activity(message) { $("activity-label").textContent = message; }

function updateServiceUI() {
    const available = state.connected && state.editorServices === true;
    const checking = state.editorServices === null;
    $("diagnostic-source").textContent = checking ? "CHECKING" : available ? "LSP" : "COMPILER";
    $("service-notice").hidden = checking || available;
    $("feature-notes").hidden = !available;
    $("format-button").disabled = !available;
    $("check-authoring").disabled = !available;
    $("refresh-outline").disabled = !available;
    $("inspect-symbol").disabled = !available;
    $("show-hints").disabled = !available || !state.editor;
    $("show-semantics").disabled = !available || !state.editor;
    for (const name of ["inspect", "authoring"]) {
        const tab = document.querySelector(`[data-tab="${name}"]`);
        tab.disabled = !available;
        tab.title = available ? "" : checking ? "Checking whether this service supports the current source." : "This service currently supports pure functions.";
    }
    if (!available && (!$("inspect-panel").hidden || !$("authoring-panel").hidden)) selectTab("problems");
    state.editor?.updateOptions({ inlayHints: { enabled: available && $("show-hints").checked ? "on" : "off" }, "semanticHighlighting.enabled": available && $("show-semantics").checked });
    if (!state.editor && $("editor-notice").textContent.startsWith("Plain-text mode:")) {
        $("editor-notice").textContent = available
            ? "Plain-text mode: Monaco could not load from the CDN. Compile, format, evaluate, authoring checks and symbol inspection are available; inline editor features need Monaco."
            : "Plain-text mode: Monaco could not load from the CDN. Compilation, automatic diagnostics, expression evaluation and downloads are available.";
    }
}

function invalidateServices() {
    state.analysisTicket++;
    state.editorServices = null;
    clearAuthoring("Checking whether authoring services support the current source.");
    clearInspection("Checking whether symbol inspection supports the current source.");
    updateServiceUI();
}

function clearCompilation(message) {
    state.compileTicket++;
    state.gallina = "";
    $("copy-output").disabled = true;
    $("download-output").disabled = true;
    $("compile-button").disabled = false;
    $("gallina-output").textContent = "// Compile the current source to inspect its translation.";
    $("compile-summary").textContent = message;
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

async function api(path, body, { keepalive = false } = {}) {
    if (!token) throw new Error("Open the complete launch URL printed by vela-playground to connect.");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch(path, {
            method: "POST", headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
            body: JSON.stringify(body), credentials: "omit", cache: "no-store", redirect: "error",
            signal: controller.signal, keepalive,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : `Local service returned HTTP ${response.status}.`);
        return data;
    } catch (error) {
        if (error.name === "AbortError") throw new Error("The local service timed out. Reconnect if language services stopped responding.");
        throw error;
    } finally { clearTimeout(timer); }
}

function snapshot() { return { text: state.text, version: state.version, generation: state.generation }; }
function current(captured) { return captured.version === state.version && captured.text === state.text && captured.generation === state.generation; }

function clearDiagnostics(message = "Checking the current buffer…") {
    $("problem-count").textContent = "0";
    $("problem-count").classList.remove("has-problems");
    $("diagnostics").replaceChildren(element("p", "muted-message", message));
    if (state.model && window.monaco) monaco.editor.setModelMarkers(state.model, "vela", []);
}

function publishDiagnostics(params, generation, fromCompiler = false) {
    if ((!fromCompiler && state.editorServices !== true) || generation !== state.generation || params.uri !== DOCUMENT_URI || params.version !== state.version) return;
    const diagnostics = params.diagnostics || [];
    $("problem-count").textContent = String(diagnostics.length);
    $("problem-count").classList.toggle("has-problems", diagnostics.length > 0);
    if (state.model && window.monaco) {
        monaco.editor.setModelMarkers(state.model, "vela", diagnostics.map((diagnostic) => ({
            ...toRange(diagnostic.range), message: diagnostic.message,
            severity: diagnostic.severity === 2 ? monaco.MarkerSeverity.Warning : monaco.MarkerSeverity.Error,
            source: diagnostic.source || "Vela compiler", code: diagnostic.code,
        })));
    }
    if (!diagnostics.length) {
        const clean = element("div", "diagnostic-clean", "No error reported for the current source.");
        clean.append(element("small", "", "This is a development check, with no kernel or production acceptance verdict."));
        $("diagnostics").replaceChildren(clean);
        activity("Current buffer checked");
        return;
    }
    $("diagnostics").replaceChildren(...diagnostics.map((diagnostic) => {
        const item = element("button", "diagnostic-item");
        item.type = "button";
        const code = diagnostic.code ? ` · ${diagnostic.severity === 2 ? "warning" : "error"} ${diagnostic.code}` : "";
        item.append(element("span", "diagnostic-site", `playground.vela · ${diagnostic.range.start.line + 1}:${diagnostic.range.start.character + 1}${code}`));
        item.append(element("span", "diagnostic-message", diagnostic.message));
        item.addEventListener("click", () => {
            if (state.editor) {
                const range = toRange(diagnostic.range);
                state.editor.setSelection(range);
                state.editor.revealRangeInCenter(range);
                state.editor.focus();
            } else $("source-fallback").focus();
        });
        return item;
    }));
    activity(`${diagnostics.length} problem${diagnostics.length === 1 ? "" : "s"} in current buffer`);
}

function compilerDiagnostics(result, captured) {
    if (!current(captured)) return;
    const error = result.error;
    const position = error ? compilerPosition(error.line, error.column) : null;
    const findings = result.ok ? result.findings : [];
    if (!Array.isArray(findings)) throw new Error("The compiler returned incomplete naming findings.");
    publishDiagnostics({ uri: DOCUMENT_URI, version: captured.version, diagnostics: error ? [{
        range: { start: position, end: position }, severity: 1, message: errorText(error),
        source: "Vela compiler",
    }] : findings.map((finding) => {
        const start = compilerPosition(finding.line, finding.column);
        return { range: { start, end: start }, severity: 2, message: finding.message,
            code: finding.code, source: "Vela naming lint" };
    }) }, captured.generation, true);
}

async function wire(session, message, generation) {
    const response = await api("/api/lsp", { session, message });
    if (!Array.isArray(response.messages)) throw new Error("The language server returned an invalid response.");
    for (const item of response.messages) {
        if (item.method === "textDocument/publishDiagnostics") publishDiagnostics(item.params, generation);
    }
    if (!("id" in message)) return undefined;
    const reply = response.messages.find((item) => item.id === message.id && "jsonrpc" in item);
    if (!reply) throw new Error("The language server returned no correlated reply.");
    if (reply.error) {
        const error = new Error(reply.error.message || "The language server refused this request.");
        error.lspCode = reply.error.code;
        throw error;
    }
    return reply.result;
}

async function closeSession(session, options = {}) {
    try {
        await api("/api/close", { session }, options);
    } catch { /* Expired sessions and closing tabs also have bounded server-side expiry. */ }
}

function enqueue(operation) {
    const result = state.queue.then(operation);
    state.queue = result.catch(() => undefined);
    return result;
}

function disconnected(error, generation) {
    if (generation !== state.generation) return;
    state.connected = false;
    invalidateServices();
    status(error.message || "Local language services disconnected.", true);
    clearDiagnostics("Language services are disconnected. Compile and expression evaluation remain available.");
    clearAuthoring("Connection unavailable. Check style again when the local service is ready.");
    clearInspection("Language services are disconnected. Reconnect to inspect symbols.");
}

async function connect() {
    const oldSession = state.session;
    const generation = ++state.generation;
    state.connected = false;
    clearTimeout(state.checkTimer);
    invalidateServices();
    clearCompilation("Connection changed. Compile again for current output.");
    clearEvaluation("Connection changed. Evaluate again for a current result.");
    clearDiagnostics("Checking the current buffer…");
    clearAuthoring("Connection changed. Check style again for the current buffer.");
    clearInspection("Connecting to the language server…");
    state.connected = false;
    state.session = null;
    state.opened = false;
    state.syncedVersion = 0;
    status("Connecting to the local language server…");
    if (oldSession) closeSession(oldSession);
    const pending = (async () => {
        const available = await api("/api/capabilities", {});
        if (generation !== state.generation) return;
        if (available.mathematical !== true) throw new Error("The playground service is missing dependent mathematics. Restart vela-playground and reopen its launch URL.");
        const response = await api("/api/session", {});
        const session = response.session;
        let adopted = false;
        try {
            if (generation !== state.generation) return;
            const initialized = await wire(session, {
                jsonrpc: "2.0", id: ++state.requestId, method: "initialize",
                params: { processId: null, rootUri: null, capabilities: { general: { positionEncodings: ["utf-16"] } } },
            }, generation);
            if (generation !== state.generation) return;
            await wire(session, { jsonrpc: "2.0", method: "initialized", params: {} }, generation);
            if (generation !== state.generation) return;
            state.session = session;
            state.capabilities = initialized.capabilities;
            adopted = true;
            state.connected = true;
            status("Language server connected");
            scheduleCheck(0);
            if (!$("inspect-panel").hidden) refreshOutline();
        } finally {
            if (!adopted) await closeSession(session);
        }
    })();
    state.connection = pending;
    try { await pending; }
    catch (error) { disconnected(error, generation); }
}

async function synchronize(captured) {
    if (state.editorServices !== true || !current(captured) || !state.connected) return false;
    if (state.syncedVersion === captured.version) return true;
    const message = state.opened
        ? { jsonrpc: "2.0", method: "textDocument/didChange", params: { textDocument: { uri: DOCUMENT_URI, version: captured.version }, contentChanges: [{ text: captured.text }] } }
        : { jsonrpc: "2.0", method: "textDocument/didOpen", params: { textDocument: { uri: DOCUMENT_URI, languageId: "vela", version: captured.version, text: captured.text } } };
    await wire(state.session, message, captured.generation);
    if (captured.generation !== state.generation) return false;
    state.opened = true;
    state.syncedVersion = captured.version;
    return current(captured);
}

async function languageQuery(method, params = {}, captured = snapshot(), cancellation = null) {
    if (state.editorServices !== true) return undefined;
    try {
        await state.connection;
        return await enqueue(async () => {
            if (!current(captured) || cancellation?.isCancellationRequested || !state.connected) return undefined;
            if (!await synchronize(captured)) return undefined;
            const result = await wire(state.session, {
                jsonrpc: "2.0", id: ++state.requestId, method,
                params: { textDocument: { uri: DOCUMENT_URI }, ...params },
            }, captured.generation);
            return current(captured) && !cancellation?.isCancellationRequested ? result : undefined;
        });
    } catch (error) {
        if (error.lspCode !== undefined) {
            if (current(captured)) activity(`Language service refused: ${error.message}`);
        } else disconnected(error, captured.generation);
        return undefined;
    }
}

async function acceptAnalysis(result, captured, ticket) {
    if (!current(captured) || ticket !== state.analysisTicket) return;
    if (typeof result.editorServices !== "boolean") throw new Error("The compiler returned incomplete editor-service availability.");
    state.editorServices = state.connected ? result.editorServices : null;
    updateServiceUI();
    compilerDiagnostics(result, captured);
    if (state.editorServices === true) {
        try {
            await enqueue(() => synchronize(captured));
            if (current(captured) && ticket === state.analysisTicket && !$("inspect-panel").hidden) refreshOutline();
        } catch (error) {
            if (current(captured) && ticket === state.analysisTicket) disconnected(error, captured.generation);
        }
    }
}

function scheduleCheck(delay = 400) {
    clearTimeout(state.checkTimer);
    const ticket = ++state.analysisTicket;
    state.checkTimer = setTimeout(async () => {
        const captured = snapshot();
        try {
            await state.connection;
            if (!current(captured) || ticket !== state.analysisTicket || !state.connected) return;
            const [result, hash] = await Promise.all([api("/api/compile", { source: captured.text }), expectedHash(captured.text)]);
            if (!current(captured) || ticket !== state.analysisTicket) return;
            if (result.sourceHash !== hash) throw new Error("The compiler response does not match the requested source.");
            await acceptAnalysis(result, captured, ticket);
        } catch (error) {
            if (!current(captured) || ticket !== state.analysisTicket) return;
            invalidateServices();
            clearDiagnostics(`Source check unavailable: ${error.message}`);
            activity("Source check unavailable; compile or reconnect to retry");
        }
    }, delay);
}

function clearEvaluation(message = "Evaluate an expression against the current source.") {
    state.evaluateTicket++;
    $("evaluate-button").disabled = false;
    $("console-result").replaceChildren(element("p", "muted-message", message));
}

function sourceChanged(text) {
    if (text === state.text) return;
    state.text = text;
    state.version++;
    invalidateServices();
    clearCompilation("Output cleared because the source changed.");
    clearEvaluation();
    clearAuthoring("Source changed. Check style again for a current preview.");
    clearInspection("Source changed. Refresh the outline to inspect this buffer.");
    if (state.undoSource && state.undoSource.after !== text) {
        state.undoSource = null;
        $("undo-buffer").disabled = true;
    }
    clearDiagnostics(state.connected ? "Checking the current buffer…" : "Language services are not connected.");
    activity("Source changed");
    scheduleCheck();
}

function setSource(text) {
    $("source-fallback").value = text;
    if (state.model) state.model.setValue(text);
    else sourceChanged(text);
}

function toPosition(position) { return { line: position.lineNumber - 1, character: position.column - 1 }; }
function toRange(range) { return { startLineNumber: range.start.line + 1, startColumn: range.start.character + 1, endLineNumber: range.end.line + 1, endColumn: range.end.character + 1 }; }
function fromRange(range) { return { start: { line: range.startLineNumber - 1, character: range.startColumn - 1 }, end: { line: range.endLineNumber - 1, character: range.endColumn - 1 } }; }

function sourceOffset(text, position) {
    const lines = text.split(/\r\n|\n|\r/);
    const separators = text.match(/\r\n|\n|\r/g) || [];
    let offset = 0;
    for (let line = 0; line < position.line; line++) offset += lines[line].length + separators[line].length;
    return offset + position.character;
}

function sourcePosition(text, offset) {
    const lines = text.slice(0, offset).split(/\r\n|\n|\r/);
    return { line: lines.length - 1, character: lines.at(-1).length };
}

function compilerPosition(line, column) {
    const sourceLine = state.text.split(/\r\n|\n|\r/)[line - 1] || "";
    return { line: line - 1, character: Array.from(sourceLine).slice(0, column - 1).join("").length };
}

function revealSource(range) {
    if (state.editor) {
        state.editor.setSelection(toRange(range));
        state.editor.revealRangeInCenter(toRange(range));
        state.editor.focus();
    } else {
        const textarea = $("source-fallback");
        textarea.focus();
        textarea.setSelectionRange(sourceOffset(state.text, range.start), sourceOffset(state.text, range.end));
        const lineHeight = Number.parseFloat(getComputedStyle(textarea).lineHeight) || 22;
        textarea.scrollTop = Math.max(0, range.start.line * lineHeight - textarea.clientHeight / 2);
        $("cursor-position").textContent = `Ln ${range.start.line + 1}, Col ${range.start.character + 1}`;
    }
}

function replaceBuffer(text, source) {
    if (text === state.text) return;
    const before = state.text;
    if (state.editor) {
        state.editor.pushUndoStop();
        state.editor.executeEdits(source, [{ range: state.model.getFullModelRange(), text }]);
        state.editor.pushUndoStop();
    } else setSource(text);
    state.undoSource = { before, after: state.text };
    $("undo-buffer").disabled = false;
}

function clearAuthoring(message) {
    state.authoringTicket++;
    state.authoring = null;
    $("check-authoring").disabled = state.editorServices !== true;
    $("apply-binding-preview").disabled = true;
    $("authoring-summary").textContent = message;
    $("authoring-findings").replaceChildren();
    $("binding-preview").textContent = "No current preview.";
}

async function checkAuthoring() {
    if (state.editorServices !== true) return;
    const captured = snapshot();
    const ticket = ++state.authoringTicket;
    const stillCurrent = () => current(captured) && ticket === state.authoringTicket;
    state.authoring = null;
    $("check-authoring").disabled = true;
    $("apply-binding-preview").disabled = true;
    $("authoring-summary").textContent = "Checking the complete source with the compiler…";
    $("authoring-findings").replaceChildren();
    $("binding-preview").textContent = "Waiting for a checked candidate…";
    try {
        const [result, hash] = await Promise.all([api("/api/authoring", { source: captured.text }), expectedHash(captured.text)]);
        if (!stillCurrent()) return;
        if (result.sourceHash !== hash) throw new Error("The authoring response does not match the requested source.");
        if (!result.ok) throw new Error(errorText(result.error));
        if (!Array.isArray(result.findings) || typeof result.bindingPreview !== "string") throw new Error("The authoring service returned an incomplete result.");
        const changed = result.bindingPreview !== captured.text;
        state.authoring = { captured, candidate: result.bindingPreview };
        $("authoring-summary").textContent = `${result.findings.length} advisory finding${result.findings.length === 1 ? "" : "s"} · source SHA-256 ${hash.slice(0, 12)} · ${changed ? "binding preview available" : "no binding edits needed"}`;
        $("authoring-findings").replaceChildren(...result.findings.map((finding) => {
            const item = element("button", "diagnostic-item advisory-item");
            item.type = "button";
            item.append(element("span", "diagnostic-site", `${finding.code} · ${finding.line}:${finding.column}`), element("span", "diagnostic-message", finding.message));
            item.addEventListener("click", () => {
                if (!current(captured)) return;
                const position = compilerPosition(finding.line, finding.column);
                revealSource({ start: position, end: position });
            });
            return item;
        }));
        $("binding-preview").textContent = result.bindingPreview;
        $("apply-binding-preview").disabled = !changed;
        activity(changed ? "Authoring check ready; review the binding preview" : "Authoring check ready; no binding edits needed");
    } catch (error) {
        if (!stillCurrent()) return;
        state.authoring = null;
        $("authoring-summary").textContent = `Authoring check unavailable: ${error.message}`;
        $("binding-preview").textContent = "No checked preview available.";
        activity("Authoring check unavailable");
    } finally { if (stillCurrent()) $("check-authoring").disabled = false; }
}

function clearInspection(message) {
    state.outlineTicket++;
    state.inspectTicket++;
    state.outlineSnapshot = null;
    state.inspectPending = false;
    $("refresh-outline").disabled = state.editorServices !== true;
    $("inspect-symbol").disabled = state.editorServices !== true;
    $("outline").replaceChildren(element("p", "muted-message", message));
    $("symbol-details").textContent = "Select a symbol from the current outline or inspect an identifier at the source cursor.";
    $("symbol-references").replaceChildren();
}

async function refreshOutline() {
    if (state.editorServices !== true) return;
    const captured = snapshot();
    clearInspection("Loading compiler-resolved symbols…");
    const ticket = ++state.outlineTicket;
    const stillCurrent = () => current(captured) && ticket === state.outlineTicket;
    $("refresh-outline").disabled = true;
    $("outline").replaceChildren(element("p", "muted-message", "Loading compiler-resolved symbols…"));
    try {
        const result = await languageQuery("textDocument/documentSymbol", {}, captured);
        if (!stillCurrent()) return;
        if (!result) {
            clearInspection("Outline unavailable. Check the connection and source, then refresh.");
            return;
        }
        state.outlineSnapshot = captured;
        const symbols = result.filter((symbol) => symbol.location?.uri === DOCUMENT_URI);
        $("outline").replaceChildren(...(symbols.length ? symbols.map((symbol) => {
            const item = element("button", "symbol-item");
            item.type = "button";
            item.append(element("span", "symbol-name", symbol.name), element("span", "symbol-site", `${symbol.kind === 12 ? "function" : symbol.kind === 14 ? "constant" : "binding"} · ${symbol.location.range.start.line + 1}:${symbol.location.range.start.character + 1}`));
            item.addEventListener("click", () => {
                if (!current(captured)) return;
                revealSource(symbol.location.range);
                inspectSymbol(symbol.location.range.start);
            });
            return item;
        }) : [element("p", "muted-message", "No resolved symbols returned for this source.")]));
    } finally { if (stillCurrent()) $("refresh-outline").disabled = false; }
}

async function inspectSymbol(position = null) {
    if (state.editorServices !== true) return;
    const captured = snapshot();
    const ticket = ++state.inspectTicket;
    const stillCurrent = () => current(captured) && ticket === state.inspectTicket;
    if (!position) position = state.editor ? toPosition(state.editor.getPosition()) : sourcePosition(state.text, $("source-fallback").selectionStart);
    $("inspect-symbol").disabled = true;
    state.inspectPending = true;
    state.inspectSelection = sourceSelectionKey();
    $("symbol-details").textContent = "Inspecting the selected identifier…";
    $("symbol-references").replaceChildren();
    try {
        const [hover, references] = await Promise.all([
            languageQuery("textDocument/hover", { position }, captured),
            languageQuery("textDocument/references", { position, context: { includeDeclaration: true } }, captured),
        ]);
        if (!stillCurrent()) return;
        if (hover === undefined || references === undefined) {
            clearInspection("Inspection unavailable. Refresh the outline when language services are ready.");
            $("symbol-details").textContent = "Inspection unavailable. Check the connection and source, then retry.";
            return;
        }
        $("symbol-details").textContent = typeof hover?.contents === "string" ? hover.contents : hover?.contents?.value || "No resolved identifier at this source position.";
        const local = (references || []).filter((reference) => reference.uri === DOCUMENT_URI);
        $("symbol-references").append(element("p", "muted-message", `${local.length} resolved occurrence${local.length === 1 ? "" : "s"}, including the declaration.`));
        const lines = captured.text.split(/\r\n|\n|\r/);
        for (const reference of local) {
            const item = element("button", "reference-item");
            item.type = "button";
            item.append(element("span", "symbol-site", `${reference.range.start.line + 1}:${reference.range.start.character + 1}`), element("span", "reference-source", lines[reference.range.start.line].trim()));
            item.addEventListener("click", () => { if (current(captured)) revealSource(reference.range); });
            $("symbol-references").append(item);
        }
    } finally {
        if (stillCurrent()) {
            state.inspectPending = false;
            $("inspect-symbol").disabled = false;
        }
    }
}

function sourceSelectionKey() {
    if (state.editor) return JSON.stringify(state.editor.getSelection());
    const source = $("source-fallback");
    return `${source.selectionStart}:${source.selectionEnd}`;
}

function sourceSelectionChanged() {
    if (state.editorServices !== true) return;
    if (!state.inspectPending || state.inspectSelection === sourceSelectionKey()) return;
    state.inspectTicket++;
    state.inspectPending = false;
    $("inspect-symbol").disabled = false;
    $("symbol-details").textContent = "Source selection changed. Inspect the current identifier again.";
    $("symbol-references").replaceChildren();
}

function download(text, name) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = element("a");
    anchor.href = url;
    anchor.download = name;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function plaintextMarkdown(text) {
    const runs = String(text).match(/`+/g) || [];
    const fence = "`".repeat(Math.max(3, ...runs.map((run) => run.length + 1)));
    return { value: `${fence}text\n${text}\n${fence}`, isTrusted: false, supportHtml: false };
}

function locations(result) {
    return (Array.isArray(result) ? result : result ? [result] : [])
        .filter((location) => location.uri === DOCUMENT_URI)
        .map((location) => ({ uri: monaco.Uri.parse(location.uri), range: toRange(location.range) }));
}

function registerLanguage() {
    monaco.languages.register({ id: "vela", extensions: [".vela"] });
    monaco.languages.setLanguageConfiguration("vela", {
        comments: { lineComment: "//" }, brackets: [["{", "}"], ["(", ")"]],
        autoClosingPairs: [{ open: "{", close: "}" }, { open: "(", close: ")" }],
        surroundingPairs: [{ open: "{", close: "}" }, { open: "(", close: ")" }],
    });
    monaco.languages.setMonarchTokensProvider("vela", {
        keywords: ["module", "public", "const", "let", "if", "else", "match", "case", "return", "definition", "alias", "ghost", "lemma", "theorem", "requires", "ensures", "decreases", "where", "proof", "assert", "by", "type", "forall", "exists", "ref", "record", "with", "is", "this"],
        typeKeywords: ["Nat", "bool", "Unit", "Type", "Prop", "Fn", "Vec", "Fin", "Eq", "TextBuilder"], tokenizer: { root: [
            [/\/\/.*$/, "comment"], [/"""[\s\S]*?"""/, "string"], [/\$"(?:\\.|[^"\\])*"/, "string"], [/"(?:\\.|[^"\\])*"/, "string"], [/\b(?:true|false)\b/, "constant"],
            [/[A-Za-z_][A-Za-z0-9_]*/, { cases: { "@keywords": "keyword", "@typeKeywords": "type", "@default": "identifier" } }],
            [/[0-9](?:_?[0-9])*/, "number"], [/=>|==|!=|<=|>=|&&|\|\||[+*\/%!=<>-]/, "operator"], [/[{}()]/, "@brackets"], [/[;,.:]/, "delimiter"],
        ] },
    });
    monaco.editor.defineTheme("vela-night", {
        base: "vs-dark", inherit: true,
        rules: [
            { token: "keyword", foreground: "C6AEED" }, { token: "type", foreground: "93C6DA" },
            { token: "identifier", foreground: "CDD7EB" }, { token: "comment", foreground: "687D85", fontStyle: "italic" },
            { token: "string", foreground: "A8D4A2" }, { token: "number", foreground: "D9BA8B" }, { token: "constant", foreground: "D9BA8B" },
            { token: "operator", foreground: "AAB6D2" }, { token: "function", foreground: "BDCDFF" },
            { token: "parameter", foreground: "B5D4DB" }, { token: "variable", foreground: "C8D4E9" },
        ], colors: {
            "editor.background": "#10141C", "editor.foreground": "#CDD7EB", "editorLineNumber.foreground": "#46536A",
            "editorLineNumber.activeForeground": "#9BABCA", "editor.selectionBackground": "#34436B80",
            "editor.inactiveSelectionBackground": "#303C5655", "editor.lineHighlightBackground": "#1B223040",
            "editorCursor.foreground": "#C5D0FF", "editorIndentGuide.background1": "#27314470",
            "editorIndentGuide.activeBackground1": "#53607A", "editorWidget.background": "#1A2130",
            "editorWidget.border": "#3C4861", "editorHoverWidget.background": "#1A2130",
            "editorHoverWidget.border": "#3C4861", "editorInlayHint.background": "#1C263555",
            "editorInlayHint.foreground": "#788CAC", "editorError.foreground": "#E49AA9",
        },
    });
    monaco.languages.registerHoverProvider("vela", {
        async provideHover(model, position, cancellation) {
            const result = await languageQuery("textDocument/hover", { position: toPosition(position) }, snapshot(), cancellation);
            if (!result) return null;
            const content = typeof result.contents === "string" ? result.contents : result.contents?.value || "";
            return { contents: [plaintextMarkdown(content)], ...(result.range ? { range: toRange(result.range) } : {}) };
        },
    });
    monaco.languages.registerDefinitionProvider("vela", {
        async provideDefinition(model, position, cancellation) {
            return locations(await languageQuery("textDocument/definition", { position: toPosition(position) }, snapshot(), cancellation));
        },
    });
    monaco.languages.registerReferenceProvider("vela", {
        async provideReferences(model, position, context, cancellation) {
            return locations(await languageQuery("textDocument/references", { position: toPosition(position), context: { includeDeclaration: context.includeDeclaration } }, snapshot(), cancellation));
        },
    });
    monaco.languages.registerDocumentSymbolProvider("vela", {
        async provideDocumentSymbols(model, cancellation) {
            const result = await languageQuery("textDocument/documentSymbol", {}, snapshot(), cancellation);
            return (result || []).map((symbol) => ({
                name: symbol.name, detail: "", kind: symbol.kind - 1, tags: [],
                range: toRange(symbol.location.range), selectionRange: toRange(symbol.location.range), children: [],
            }));
        },
    });
    monaco.languages.registerInlayHintsProvider("vela", {
        async provideInlayHints(model, range, cancellation) {
            const result = await languageQuery("textDocument/inlayHint", { range: fromRange(range) }, snapshot(), cancellation);
            return { hints: (result || []).map((hint) => ({
                position: { lineNumber: hint.position.line + 1, column: hint.position.character + 1 },
                label: hint.label, kind: monaco.languages.InlayHintKind.Type,
                paddingLeft: Boolean(hint.paddingLeft), paddingRight: Boolean(hint.paddingRight),
            })), dispose() {} };
        },
    });
    monaco.languages.registerDocumentSemanticTokensProvider("vela", {
        getLegend() { return state.capabilities.semanticTokensProvider?.legend || { tokenTypes: ["function", "parameter", "variable"], tokenModifiers: ["declaration", "readonly"] }; },
        async provideDocumentSemanticTokens(model, lastResultId, cancellation) {
            const result = await languageQuery("textDocument/semanticTokens/full", {}, snapshot(), cancellation);
            return result ? { data: new Uint32Array(result.data) } : null;
        },
        releaseDocumentSemanticTokens() {},
    });
    monaco.languages.registerDocumentFormattingEditProvider("vela", {
        async provideDocumentFormattingEdits(model, options, cancellation) {
            const result = await languageQuery("textDocument/formatting", { options: { tabSize: options.tabSize, insertSpaces: options.insertSpaces } }, snapshot(), cancellation);
            return (result || []).map((edit) => ({ range: toRange(edit.range), text: edit.newText }));
        },
    });
}

async function loadEditor() {
    try {
        window.MonacoEnvironment = { getWorkerUrl() {
            return URL.createObjectURL(new Blob([`self.MonacoEnvironment={baseUrl:${JSON.stringify(MONACO_ROOT + "/../")}};importScripts(${JSON.stringify(MONACO_ROOT + "/base/worker/workerMain.js")});`], { type: "text/javascript" }));
        } };
        await new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = `${MONACO_ROOT}/loader.js`;
            script.onload = resolve;
            script.onerror = () => reject(new Error("Monaco assets could not be loaded."));
            document.head.append(script);
            setTimeout(() => reject(new Error("Monaco assets took too long to load.")), 12000);
        });
        window.require.config({ paths: { vs: MONACO_ROOT } });
        await new Promise((resolve, reject) => {
            window.require(["vs/editor/editor.main"], resolve, reject);
            setTimeout(() => reject(new Error("The code editor took too long to initialize.")), 15000);
        });
        registerLanguage();
        state.model = monaco.editor.createModel(state.text, "vela", monaco.Uri.parse(DOCUMENT_URI));
        $("editor").hidden = false;
        state.editor = monaco.editor.create($("editor"), {
            model: state.model, theme: "vela-night", automaticLayout: true,
            fontFamily: '"Cascadia Code", "SFMono-Regular", Consolas, "Liberation Mono", monospace',
            fontSize: 12, lineHeight: 22, padding: { top: 22, bottom: 20 },
            minimap: { enabled: false }, scrollBeyondLastLine: false, smoothScrolling: false,
            renderLineHighlight: "line", lineNumbersMinChars: 3, glyphMargin: false,
            folding: false, fontLigatures: false, tabSize: 4, insertSpaces: true,
            wordWrap: "off", inlayHints: { enabled: state.editorServices === true && $("show-hints").checked ? "on" : "off" }, "semanticHighlighting.enabled": state.editorServices === true && $("show-semantics").checked,
            quickSuggestions: false, suggestOnTriggerCharacters: false, wordBasedSuggestions: "off",
            ariaLabel: "Vela source editor", contextmenu: true,
        });
        state.model.onDidChangeContent(() => {
            $("source-fallback").value = state.model.getValue();
            sourceChanged(state.model.getValue());
        });
        state.editor.onDidChangeCursorPosition(({ position }) => {
            $("cursor-position").textContent = `Ln ${position.lineNumber}, Col ${position.column}`;
            sourceSelectionChanged();
        });
        state.editor.onDidChangeCursorSelection(sourceSelectionChanged);
        state.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, compile);
        $("source-fallback").hidden = true;
        $("editor-notice").hidden = true;
        updateServiceUI();
        scheduleCheck(0);
    } catch (error) {
        state.editor?.dispose();
        state.model?.dispose();
        state.editor = null;
        state.model = null;
        $("show-hints").disabled = true;
        $("show-semantics").disabled = true;
        $("editor").hidden = true;
        $("source-fallback").hidden = false;
        $("source-fallback").value = state.text;
        $("editor-notice").textContent = "Plain-text mode: Monaco could not load from the CDN. Compile, format, evaluate, authoring checks and symbol inspection are available; inline editor features need Monaco.";
        $("editor-notice").hidden = false;
        updateServiceUI();
    }
}

function selectTab(name) {
    if (state.editorServices !== true && ["inspect", "authoring"].includes(name)) return;
    document.querySelectorAll("[data-tab]").forEach((button) => {
        const selected = button.dataset.tab === name;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", String(selected));
        button.tabIndex = selected ? 0 : -1;
        $(`${button.dataset.tab}-panel`).hidden = !selected;
    });
    if (name === "inspect" && !state.outlineSnapshot) refreshOutline();
}

function errorText(error) {
    if (!error || typeof error === "string") return error || "The compiler refused this input.";
    return `${error.kind || "error"} at ${error.line || 1}:${error.column || 1}: ${error.message || "The compiler refused this input."}`;
}

async function expectedHash(text) {
    const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function compile() {
    const captured = snapshot();
    const ticket = ++state.compileTicket;
    clearTimeout(state.checkTimer);
    const analysisTicket = ++state.analysisTicket;
    const stillCurrent = () => current(captured) && ticket === state.compileTicket;
    selectTab("gallina");
    state.gallina = "";
    $("copy-output").disabled = true;
    $("download-output").disabled = true;
    $("compile-button").disabled = true;
    $("compile-summary").textContent = "Compiling the current source…";
    $("gallina-output").textContent = "";
    activity("Compiling…");
    try {
        const [result, hash] = await Promise.all([api("/api/compile", { source: captured.text }), expectedHash(captured.text)]);
        if (!stillCurrent()) return;
        if (result.sourceHash !== hash) throw new Error("The compiler response does not match the requested source.");
        await acceptAnalysis(result, captured, analysisTicket);
        if (!stillCurrent()) return;
        if (!result.ok) {
            $("compile-summary").textContent = "Compilation refused; no generated output.";
            $("gallina-output").textContent = errorText(result.error);
            activity("Compiler refused the source");
            return;
        }
        state.gallina = result.gallina;
        $("gallina-output").textContent = result.gallina;
        $("compile-summary").textContent = `${result.module} · unqualified translation; kernel replay separate · SHA-256 ${hash.slice(0, 12)}`;
        $("copy-output").disabled = false;
        $("download-output").disabled = false;
        activity("Gallina output ready");
    } catch (error) {
        if (!stillCurrent()) return;
        if (analysisTicket === state.analysisTicket) invalidateServices();
        $("compile-summary").textContent = "Compilation unavailable; no generated output.";
        $("gallina-output").textContent = error.message;
        activity("Compilation unavailable");
    } finally { if (stillCurrent()) $("compile-button").disabled = false; }
}

async function evaluate(event) {
    event?.preventDefault();
    const captured = snapshot();
    const expression = $("expression").value;
    const valueType = $("value-type").value;
    const ticket = ++state.evaluateTicket;
    const stillCurrent = () => current(captured) && ticket === state.evaluateTicket && expression === $("expression").value && valueType === $("value-type").value;
    selectTab("console");
    $("evaluate-button").disabled = true;
    $("console-result").replaceChildren(element("p", "muted-message", "Evaluating the expression against the current source…"));
    activity("Evaluating…");
    try {
        const [result, hash] = await Promise.all([api("/api/evaluate", { source: captured.text, expression, valueType }), expectedHash(captured.text)]);
        if (!stillCurrent()) return;
        if (result.sourceHash !== hash) throw new Error("The evaluation response does not match the requested source.");
        const card = element("div", `result-card${result.ok ? "" : " error"}`);
        card.append(element("p", "result-caption", result.ok ? "COMPILE-TIME RESULT" : "EVALUATION REFUSED"));
        card.append(element("p", "result-expression", `› ${expression}`));
        card.append(element("p", "result-value", result.ok ? result.value : errorText(result.error)));
        if (result.ok) card.append(element("div", "result-type", `: ${result.valueType}`));
        card.append(element("div", "result-identity", `Source SHA-256 ${hash.slice(0, 12)} · compile-time evaluation; no kernel verdict`));
        $("console-result").replaceChildren(card);
        activity(result.ok ? "Compile-time value ready" : "Compiler refused the expression");
    } catch (error) {
        if (!stillCurrent()) return;
        const card = element("div", "result-card error");
        card.append(element("p", "result-caption", "EVALUATION UNAVAILABLE"), element("p", "result-value", error.message));
        $("console-result").replaceChildren(card);
        activity("Evaluation unavailable");
    } finally { if (stillCurrent()) $("evaluate-button").disabled = false; }
}

async function format() {
    if (state.editorServices !== true) return;
    const captured = snapshot();
    $("format-button").disabled = true;
    try {
        const edits = await languageQuery("textDocument/formatting", { options: { tabSize: 4, insertSpaces: true } }, captured);
        if (!current(captured)) return;
        if (!edits) { activity("Formatting unavailable; check the connection"); return; }
        if (!edits.length) { activity("No formatting edit returned"); return; }
        const ordered = edits.map((edit) => ({ start: sourceOffset(captured.text, edit.range.start), end: sourceOffset(captured.text, edit.range.end), text: edit.newText })).sort((left, right) => right.start - left.start);
        let text = captured.text;
        for (const edit of ordered) text = text.slice(0, edit.start) + edit.text + text.slice(edit.end);
        replaceBuffer(text, "vela-format");
        activity("Canonical formatting applied");
    } finally { updateServiceUI(); }
}

$("source-fallback").addEventListener("input", () => sourceChanged($("source-fallback").value));
$("source-fallback").addEventListener("select", sourceSelectionChanged);
$("source-fallback").addEventListener("keyup", () => {
    const position = sourcePosition(state.text, $("source-fallback").selectionStart);
    $("cursor-position").textContent = `Ln ${position.line + 1}, Col ${position.character + 1}`;
    sourceSelectionChanged();
});
$("source-fallback").addEventListener("click", sourceSelectionChanged);
$("source-fallback").addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
        event.preventDefault();
        const source = $("source-fallback");
        source.setRangeText("    ", source.selectionStart, source.selectionEnd, "end");
        sourceChanged(source.value);
    }
});
$("expression").addEventListener("input", () => clearEvaluation("Expression changed. Evaluate again for a current result."));
$("value-type").addEventListener("change", () => clearEvaluation("Result type changed. Evaluate again for a current result."));
$("evaluate-form").addEventListener("submit", evaluate);
$("compile-button").addEventListener("click", compile);
$("format-button").addEventListener("click", format);
$("reconnect-button").addEventListener("click", connect);
$("check-authoring").addEventListener("click", checkAuthoring);
$("apply-binding-preview").addEventListener("click", () => {
    const preview = state.authoring;
    if (state.editorServices !== true || !preview || !current(preview.captured) || preview.candidate === state.text) {
        clearAuthoring("Preview is no longer current. Check style again before applying an edit.");
        return;
    }
    replaceBuffer(preview.candidate, "vela-binding-preview");
    activity("Explicit binding preview applied; undo is available");
});
$("undo-buffer").addEventListener("click", () => {
    const previous = state.undoSource;
    if (!previous || previous.after !== state.text) return;
    if (state.editor) state.editor.trigger("vela-buffer-undo", "undo", null);
    else setSource(previous.before);
    state.undoSource = null;
    $("undo-buffer").disabled = true;
    activity("Prior source buffer restored");
});
$("refresh-outline").addEventListener("click", refreshOutline);
$("inspect-symbol").addEventListener("click", () => inspectSymbol());
$("show-hints").addEventListener("change", updateServiceUI);
$("show-semantics").addEventListener("change", updateServiceUI);
$("download-source").addEventListener("click", () => { download(state.text, "playground.vela"); activity("Source download requested"); });
$("download-output").addEventListener("click", () => {
    if (!state.gallina) return;
    download(state.gallina, "playground.v");
    activity("Gallina download requested");
});
$("examples").addEventListener("change", () => {
    const example = examples[$("examples").value];
    $("expression").value = example.expression;
    $("value-type").value = example.valueType;
    clearEvaluation();
    setSource(example.source);
    state.editor?.setPosition({ lineNumber: 1, column: 1 });
    activity("Example loaded");
});
$("copy-output").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(state.gallina); activity("Gallina output copied"); }
    catch { activity("Clipboard unavailable; select the output to copy it"); }
});
document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => selectTab(button.dataset.tab));
    button.addEventListener("keydown", (event) => {
        const tabs = [...document.querySelectorAll("[data-tab]")].filter((tab) => !tab.disabled);
        const index = tabs.indexOf(button);
        let next;
        if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
        else if (event.key === "ArrowLeft") next = tabs[(index + tabs.length - 1) % tabs.length];
        else if (event.key === "Home") next = tabs[0];
        else if (event.key === "End") next = tabs[tabs.length - 1];
        if (next) { event.preventDefault(); selectTab(next.dataset.tab); next.focus(); }
    });
});
document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !state.editor?.hasTextFocus()) {
        event.preventDefault();
        if (document.activeElement === $("expression")) evaluate();
        else compile();
    }
    if (event.shiftKey && event.altKey && event.key.toLowerCase() === "f" && !state.editor?.hasTextFocus()) { event.preventDefault(); format(); }
});
window.addEventListener("pagehide", () => {
    if (state.session) closeSession(state.session, { keepalive: true });
});

updateServiceUI();
connect();
loadEditor();
