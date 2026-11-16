/**
 * Local stdio ACP v1 bridge for one Harness session per process.
 *
 * Wire behavior follows the subset in eval-support/PROTOCOL.md. Session state
 * remains owned by dsh-agent/dsh-session and durable events by the configured
 * session-persistence plugin.
 */

import { randomUUID } from 'node:crypto'
import { createInterface } from 'node:readline'
import { isAbsolute } from 'node:path'
import type { Context } from 'cordis'
import Schema from 'schemastery'
import { SessionId } from '@deepseek-ai/dsh-session'
import type { Session, SessionEvent, TurnEndReason } from '@deepseek-ai/dsh-session'
import type { Agent } from '@deepseek-ai/dsh-agent'
import type { StreamChunk, TextBlock } from '@deepseek-ai/dsh-llm'

const RpcIdSchema = Schema.union([String, Number, Schema.const(null)])

const RpcEnvelopeSchema = Schema.object({
  jsonrpc: Schema.const('2.0').required(),
  id: RpcIdSchema,
  method: Schema.string().required(),
  params: Schema.any<unknown>(),
})

const InitializeParamsSchema = Schema.object({
  protocolVersion: Schema.number().required(),
  clientCapabilities: Schema.any<unknown>(),
})

const SessionParamsSchema = Schema.object({
  cwd: Schema.string().required(),
  mcpServers: Schema.array(Schema.any<unknown>()).required(),
  additionalDirectories: Schema.array(String),
})

const LoadParamsSchema = Schema.object({
  sessionId: Schema.string().required(),
  cwd: Schema.string().required(),
  mcpServers: Schema.array(Schema.any<unknown>()).required(),
  additionalDirectories: Schema.array(String),
})

const PromptBlockSchema = Schema.object({
  type: Schema.const('text').required(),
  text: Schema.string().required(),
})

const PromptParamsSchema = Schema.object({
  sessionId: Schema.string().required(),
  prompt: Schema.array(PromptBlockSchema).required(),
})

const CancelParamsSchema = Schema.object({
  sessionId: Schema.string().required(),
})

type RpcId = string | number | null
type RpcEnvelope = Schemastery.TypeT<typeof RpcEnvelopeSchema>
type InitializeParams = Schemastery.TypeT<typeof InitializeParamsSchema>
type SessionParams = Schemastery.TypeT<typeof SessionParamsSchema>
type LoadParams = Schemastery.TypeT<typeof LoadParamsSchema>
type PromptParams = Schemastery.TypeT<typeof PromptParamsSchema>
type CancelParams = Schemastery.TypeT<typeof CancelParamsSchema>
type TextPrompt = TextBlock
type SlotState = 'empty' | 'creating' | 'loading' | 'ready' | 'closed'

interface ActivePrompt {
  id: RpcId
  agent: Agent
  sawRunning: boolean
  turnEndReason?: TurnEndReason
  error?: Error
  settled: boolean
  cancelSent: boolean
  complete: Promise<void>
  completeOnce: () => void
}

interface RpcErrorShape {
  code: number
  message: string
  data?: unknown
}

class RpcError extends Error {
  constructor(readonly rpc: RpcErrorShape) {
    super(rpc.message)
  }
}

function parseSchema<T>(schema: unknown, value: unknown): T {
  try {
    return (schema as (input: unknown) => T)(value)
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error)
    throw invalidParams(detail)
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function invalidParams(message: string): RpcError {
  return new RpcError({ code: -32602, message })
}

function serverError(error: unknown): RpcError {
  const message = error instanceof Error ? error.message : String(error)
  const code = isRecord(error) && typeof error.code === 'string' ? error.code : undefined
  return new RpcError({
    code: -32000,
    message,
    ...code !== undefined ? { data: { code } } : {},
  })
}

function hasOwn(record: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key)
}

function isRpcId(value: unknown): value is RpcId {
  return value === null || typeof value === 'string' || typeof value === 'number'
}

function errorMessage(error: unknown): { code: number; message: string; data?: unknown } {
  return error instanceof RpcError
    ? error.rpc
    : serverError(error).rpc
}

function textContent(blocks: TextPrompt[]): TextBlock[] {
  return blocks.map(block => ({ type: 'text', text: block.text }))
}

/** Install a stdio ACP v1 bridge on the supplied Harness context. */
export async function apply(ctx: Context, options: { model: string }): Promise<void> {
  if (typeof options.model !== 'string' || options.model.length === 0) {
    throw new TypeError('ACP bridge requires a non-empty model name')
  }

  const startupCwd = process.cwd()
  let slot: SlotState = 'empty'
  let initialized = false
  let outputOpen = true
  let agent: Agent | undefined
  let sessionId: string | undefined
  let activePrompt: ActivePrompt | undefined
  let shuttingDown: Promise<void> | undefined

  const writeProtocol = (message: unknown): void => {
    if (!outputOpen) return
    try {
      process.stdout.write(`${JSON.stringify(message)}\n`)
    } catch (error: unknown) {
      process.stderr.write(`ACP stdout write failed: ${error instanceof Error ? error.message : String(error)}\n`)
      outputOpen = false
    }
  }

  const writeResponse = (id: RpcId, result: unknown): void => {
    writeProtocol({ jsonrpc: '2.0', id, result })
  }

  const writeError = (id: RpcId | null, error: unknown): void => {
    writeProtocol({ jsonrpc: '2.0', id, error: errorMessage(error) })
  }

  const update = (updateValue: Record<string, unknown>): void => {
    if (!sessionId) return
    writeProtocol({
      jsonrpc: '2.0',
      method: 'session/update',
      params: { sessionId, update: updateValue },
    })
  }

  const writeTextUpdate = (
    session: Session,
    kind: 'user_message_chunk' | 'agent_message_chunk' | 'agent_thought_chunk',
    text: string,
  ): void => {
    if (agent?.session !== session) return
    update({ sessionUpdate: kind, content: { type: 'text', text } })
  }

  const replayEvent = (session: Session, event: SessionEvent): void => {
    if (agent?.session !== session) return
    switch (event.type) {
      case 'user/message': {
        for (const block of event.data.content) {
          if (block.type === 'text') writeTextUpdate(session, 'user_message_chunk', block.text)
        }
        break
      }
      case 'assistant/chunk': {
        const chunk: StreamChunk = event.data.chunk
        switch (chunk.type) {
          case 'text-delta':
            writeTextUpdate(session, 'agent_message_chunk', chunk.text)
            break
          case 'reasoning-delta':
            writeTextUpdate(session, 'agent_thought_chunk', chunk.text)
            break
          default:
            break
        }
        break
      }
      case 'tool/call':
        update({
          sessionUpdate: 'tool_call',
          toolCallId: event.data.callId,
          title: event.data.name,
          status: 'in_progress',
        })
        break
      case 'tool/result':
        update({
          sessionUpdate: 'tool_call_update',
          toolCallId: event.data.callId,
          status: event.data.isError ? 'failed' : 'completed',
        })
        break
      default:
        break
    }
  }

  const settlePrompt = (current: ActivePrompt): void => {
    if (current.settled || activePrompt !== current) return
    const reason = current.turnEndReason
    if (!reason) return
    current.settled = true
    activePrompt = undefined
    switch (reason.kind) {
      case 'completed':
        writeResponse(current.id, { stopReason: 'end_turn' })
        break
      case 'max-tokens':
        writeResponse(current.id, { stopReason: 'max_tokens' })
        break
      case 'aborted':
        writeResponse(current.id, { stopReason: 'cancelled' })
        break
      case 'error':
        writeError(current.id, new RpcError({
          code: -32000,
          message: current.error?.message ?? reason.message,
          ...reason.code !== undefined ? { data: { code: reason.code } } : {},
        }))
        break
      case 'disposed':
        writeError(current.id, new RpcError({ code: -32000, message: 'agent was disposed before the prompt completed' }))
        break
      default:
        break
    }
    current.completeOnce()
  }

  const onStatus = (source: Agent, status: string): void => {
    const current = activePrompt
    if (!current || source !== current.agent) return
    if (status === 'running') {
      current.sawRunning = true
      return
    }
    if (status === 'disposed') {
      current.turnEndReason = { kind: 'disposed' }
      settlePrompt(current)
      return
    }
    if (status === 'idle' && current.sawRunning) settlePrompt(current)
  }

  const onTurnEnd = (source: Agent, _turn: number, reason: TurnEndReason): void => {
    if (activePrompt?.agent === source) activePrompt.turnEndReason = reason
  }

  const onAgentError = (source: Agent, _turn: number, _step: number, error: Error): void => {
    if (activePrompt?.agent === source) activePrompt.error = error
  }

  const onStreamChunk = (source: Agent, _turn: number, _step: number, chunk: StreamChunk): void => {
    if (!activePrompt || activePrompt.agent !== source) return
    switch (chunk.type) {
      case 'text-delta':
        writeTextUpdate(source.session, 'agent_message_chunk', chunk.text)
        break
      case 'reasoning-delta':
        writeTextUpdate(source.session, 'agent_thought_chunk', chunk.text)
        break
      default:
        break
    }
  }

  const onSessionEvent = (session: Session, event: SessionEvent): void => {
    if (!activePrompt || activePrompt.agent.session !== session) return
    if (event.type === 'tool/call') {
      update({
        sessionUpdate: 'tool_call',
        toolCallId: event.data.callId,
        title: event.data.name,
        status: 'in_progress',
      })
    } else if (event.type === 'tool/result') {
      update({
        sessionUpdate: 'tool_call_update',
        toolCallId: event.data.callId,
        status: event.data.isError ? 'failed' : 'completed',
      })
    }
  }

  const notifyUserPrompt = (blocks: TextPrompt[]): void => {
    for (const block of blocks) {
      update({ sessionUpdate: 'user_message_chunk', content: { type: 'text', text: block.text } })
    }
  }

  const validateSessionParams = (raw: unknown): SessionParams => {
    const params = parseSchema<SessionParams>(SessionParamsSchema, raw)
    validateWorkspace(params.cwd, params.mcpServers, params.additionalDirectories)
    return params
  }

  const validateWorkspace = (
    cwd: string,
    mcpServers: unknown[],
    additionalDirectories: string[] | undefined,
  ): void => {
    if (!isAbsolute(cwd) || cwd !== startupCwd) throw invalidParams('cwd must be the absolute startup directory')
    if (mcpServers.length !== 0) throw invalidParams('mcpServers must be empty')
    if (additionalDirectories !== undefined && additionalDirectories.length !== 0) {
      throw invalidParams('additionalDirectories must be empty')
    }
  }

  const requireReadyAgent = (requestedSessionId: string): Agent => {
    if (slot !== 'ready' || !agent || !sessionId || sessionId !== requestedSessionId) {
      throw invalidParams('unknown session')
    }
    return agent
  }

  const createSession = (id: RpcId, raw: unknown): void => {
    if (!initialized) throw invalidParams('initialize must complete before session/new')
    const params = validateSessionParams(raw)
    if (slot !== 'empty') throw invalidParams('this process already owns a session or session operation')
    slot = 'creating'
    const newSessionId = `session-${randomUUID()}`
    try {
      const created = ctx.agents.create({
        agentId: `acp-${randomUUID()}`,
        sessionId: newSessionId,
        meta: { cwd: params.cwd },
        agentOptions: { model: options.model },
      })
      agent = created
      sessionId = created.session.id
      slot = 'ready'
      writeResponse(id, { sessionId })
    } catch (error: unknown) {
      slot = 'empty'
      agent = undefined
      sessionId = undefined
      throw error
    }
  }

  const loadSession = async (id: RpcId, raw: unknown): Promise<void> => {
    if (!initialized) throw invalidParams('initialize must complete before session/load')
    const params = parseSchema<LoadParams>(LoadParamsSchema, raw)
    validateWorkspace(params.cwd, params.mcpServers, params.additionalDirectories)
    if (slot !== 'empty') throw invalidParams('this process already owns a session or session operation')
    slot = 'loading'
    try {
      const persistence = ctx.sessionPersistence
      if (!persistence) throw new Error('session persistence is not configured')
      const requestedId = SessionId(params.sessionId)
      if (!await persistence.has(requestedId)) throw invalidParams('unknown session')
      const { meta } = await persistence.load(requestedId)
      if (meta.cwd !== startupCwd) throw invalidParams('session belongs to a different working directory')
      const resumed = await ctx.agents.resume({
        agentId: `acp-${randomUUID()}`,
        resumeSessionId: params.sessionId,
        agentOptions: { model: options.model },
      })
      agent = resumed
      sessionId = resumed.session.id
      slot = 'ready'
      for (const event of resumed.session.events) replayEvent(resumed.session, event)
      writeResponse(id, {})
    } catch (error: unknown) {
      slot = 'empty'
      agent = undefined
      sessionId = undefined
      throw error
    }
  }

  const prompt = async (id: RpcId, raw: unknown): Promise<void> => {
    const params = parseSchema<PromptParams>(PromptParamsSchema, raw)
    const currentAgent = requireReadyAgent(params.sessionId)
    if (activePrompt) throw invalidParams('a prompt is already running for this session')
    if (params.prompt.length === 0 || params.prompt.some(block => block.text.length === 0)) {
      throw invalidParams('prompt must contain non-empty text blocks')
    }
    const { promise, resolve } = Promise.withResolvers<void>()
    const current: ActivePrompt = {
      id,
      agent: currentAgent,
      sawRunning: false,
      settled: false,
      cancelSent: false,
      complete: promise,
      completeOnce: resolve,
    }
    activePrompt = current
    try {
      currentAgent.send(textContent(params.prompt))
    } catch (error: unknown) {
      activePrompt = undefined
      current.completeOnce()
      throw error
    }
    notifyUserPrompt(params.prompt)
    await current.complete
  }

  const cancel = (raw: unknown): void => {
    const params = parseSchema<CancelParams>(CancelParamsSchema, raw)
    const current = activePrompt
    if (!current || current.agent.session.id !== params.sessionId || current.cancelSent) return
    current.cancelSent = true
    current.agent.abort('ACP session/cancel')
  }

  const handleRequest = async (request: RpcEnvelope, hasId: boolean): Promise<void> => {
    if (request.method === 'session/cancel') {
      try {
        cancel(request.params)
      } catch (error: unknown) {
        if (hasId && isRpcId(request.id)) writeError(request.id, error)
      }
      return
    }
    if (!hasId || !isRpcId(request.id)) return
    const id = request.id
    try {
      switch (request.method) {
        case 'initialize': {
          const params = parseSchema<InitializeParams>(InitializeParamsSchema, request.params)
          if (!isRecord(params.clientCapabilities)) throw invalidParams('clientCapabilities must be an object')
          if (!Number.isInteger(params.protocolVersion) || params.protocolVersion < 1) {
            throw invalidParams('protocolVersion must be a positive integer')
          }
          initialized = true
          writeResponse(id, {
            protocolVersion: 1,
            agentCapabilities: { loadSession: true },
            authMethods: [],
          })
          return
        }
        case 'session/new':
          createSession(id, request.params)
          return
        case 'session/load':
          await loadSession(id, request.params)
          return
        case 'session/prompt':
          await prompt(id, request.params)
          return
        default:
          writeError(id, new RpcError({ code: -32601, message: `method not found: ${request.method}` }))
      }
    } catch (error: unknown) {
      writeError(id, error)
    }
  }

  const handleLine = async (line: string): Promise<void> => {
    let parsed: unknown
    try {
      parsed = JSON.parse(line) as unknown
    } catch {
      writeError(null, new RpcError({ code: -32700, message: 'parse error' }))
      return
    }
    let request: RpcEnvelope
    try {
      request = parseSchema<RpcEnvelope>(RpcEnvelopeSchema, parsed)
    } catch {
      writeError(null, new RpcError({ code: -32600, message: 'invalid request' }))
      return
    }
    const hasId = isRecord(parsed) && hasOwn(parsed, 'id')
    await handleRequest(request, hasId)
  }

  const shutdown = (): Promise<void> => {
    if (shuttingDown) return shuttingDown
    outputOpen = false
    slot = 'closed'
    shuttingDown = (async () => {
      const current = activePrompt
      if (!current) return
      if (!current.cancelSent) {
        current.cancelSent = true
        current.agent.abort('ACP client disconnected')
      }
      await current.complete
    })()
    return shuttingDown
  }

  await ctx.effect(() => {
    const unbind = [
      ctx.on('agent/status', onStatus),
      ctx.on('agent/turn-end', onTurnEnd),
      ctx.on('agent/error', onAgentError),
      ctx.on('agent/stream-chunk', onStreamChunk),
      ctx.on('session/event', onSessionEvent),
    ]
    const input = createInterface({ input: process.stdin, crlfDelay: Infinity })
    input.on('line', line => {
      void handleLine(line).catch(error => process.stderr.write(`ACP request failed: ${String(error)}\n`))
    })
    input.on('close', () => { void shutdown() })
    return async () => {
      input.close()
      await shutdown()
      for (const dispose of unbind) dispose()
    }
  }, 'acp.apply')
}
