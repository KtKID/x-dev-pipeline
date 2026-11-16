import { appendFile, mkdir } from 'node:fs/promises'
import { resolve, join } from 'node:path'
import { Context } from 'cordis'
import AgentRegistry from '@deepseek-ai/dsh-agent'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
import LlmService, { CallId, LlmAdapter, type GenerateOptions, type StreamChunk } from '@deepseek-ai/dsh-llm'
import SessionStore from '@deepseek-ai/dsh-session'
import SessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRegistry, { defineTool } from '@deepseek-ai/dsh-tools'
import { apply } from '../packages/acp/src/index.ts'

const storage = resolve(process.env.DSH_EVAL_STORAGE ?? '.eval-sessions')
await mkdir(storage, { recursive: true })
const event = (type: string, text: string) => appendFile(
  join(storage, 'fixture-events.jsonl'), JSON.stringify({ type, text }) + '\n',
)

class ScriptedModel extends LlmAdapter {
  async * stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    const last = options.messages.findLast(message => message.role === 'user')
    const text = last?.content.flatMap(block => block.type === 'text' ? [block.text] : []).join('') ?? ''
    const toolResult = options.messages.at(-1)?.content.some(block => block.type === 'tool-result') ?? false
    await event('generate', text)

    if (text.startsWith('tool ') && !toolResult) {
      const id = CallId('fixture-echo')
      const name = 'fixture_echo'
      const args = JSON.stringify({ text: text.slice(5) })
      yield { type: 'block-start', index: 0, blockType: 'tool-call' }
      yield { type: 'tool-call-delta', index: 0, id, name, argumentsDelta: args }
      yield { type: 'block-end', index: 0, block: { type: 'tool-call', id, name, arguments: args } }
      yield { type: 'finish', reason: { kind: 'tool-calls' } }
      return
    }

    yield { type: 'block-start', index: 0, blockType: 'reasoning' }
    yield { type: 'reasoning-delta', index: 0, text: 'Fixture thought' }
    yield { type: 'block-end', index: 0, block: { type: 'reasoning', text: 'Fixture thought' } }

    const reply = toolResult ? `Tool round: ${text}` : `Reply: ${text}`
    yield { type: 'block-start', index: 1, blockType: 'text' }
    yield { type: 'text-delta', index: 1, text: reply.slice(0, 7) }
    if (text.startsWith('hang ')) {
      const signal = options.signal
      try {
        await new Promise<never>((_resolve, reject) => {
          const abort = () => reject(new Error('fixture aborted'))
          if (signal?.aborted) abort()
          else signal?.addEventListener('abort', abort, { once: true })
        })
      } finally {
        await event('aborted', text)
      }
    }
    if (text.startsWith('error ')) {
      yield { type: 'finish', reason: { kind: 'error', message: 'fixture provider failure', code: 'FIXTURE_FAILURE' } }
      return
    }
    yield { type: 'text-delta', index: 1, text: reply.slice(7) }
    yield { type: 'block-end', index: 1, block: { type: 'text', text: reply } }
    yield { type: 'usage', usage: { inputTokens: 5, outputTokens: 3 } }
    yield { type: 'finish', reason: { kind: text.startsWith('limit ') ? 'max-tokens' : 'stop' } }
  }
}

const ctx = new Context()
await ctx.plugin(LlmService)
await ctx.plugin(SessionStore)
await ctx.plugin(SystemPrompt)
await ctx.plugin(ToolRegistry)
await ctx.plugin(AgentRegistry)
await ctx.plugin(AgentLoop, { agents: [] })
await ctx.plugin(SessionPersistence, { root: join(storage, 'sessions') })
ctx.llm.registerAdapter(['mock-eval'], new ScriptedModel())
ctx.tools.register(defineTool({
  name: 'fixture_echo',
  description: 'Record the tool input and return it',
  parameters: { text: { type: 'string', required: true } },
  async execute({ text }) {
    await event('tool', text)
    if (text.startsWith('fail ')) throw new Error('fixture tool failure')
    return [{ type: 'text', text }]
  },
}))
await apply(ctx, { model: 'mock-eval' })
