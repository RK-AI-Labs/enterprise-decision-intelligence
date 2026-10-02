"use client"

import { useState } from "react"
import { ChevronDown } from "lucide-react"

import { Chat } from "@workspace/ui/components/chat"
import type { Message } from "@workspace/ui/components/chat-message"

const suggestions = [
  "Summarize our weekly revenue trend",
  "Find customer churn risks in the last quarter",
  "Draft a launch brief for the next product cycle",
]

function buildReply(prompt: string) {
  const normalized = prompt.toLowerCase()

  if (normalized.includes("revenue") || normalized.includes("sales")) {
    return "Revenue is trending up 18% versus last month, with strongest performance in enterprise renewals and upsell expansion. I’d prioritize cross-sell automation and retention playbooks for the next two quarters."
  }

  if (
    normalized.includes("risk") ||
    normalized.includes("churn") ||
    normalized.includes("warning")
  ) {
    return "The main risk pattern is concentrated in low-usage accounts with no expansion pathway. I recommend a proactive retention sequence, executive outreach, and a health-score intervention for accounts below the activation threshold."
  }

  if (
    normalized.includes("launch") ||
    normalized.includes("brief") ||
    normalized.includes("product")
  ) {
    return "Here’s the launch brief: focus on adoption, messaging clarity, and conversion uplift. Use a two-week pilot, measure activation depth, and align sales enablement around the top three ROI use cases."
  }

  return "I’ve reviewed the current context and the strongest next move is to narrow the signal: identify the most valuable metric, compare the current trend against baseline, and propose the smallest intervention with the clearest upside."
}

export default function Page() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)

  const append = ({ content }: { role: "user"; content: string }) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content,
    }

    setMessages((prev) => [...prev, userMessage])
    void respond(content)
  }

  const respond = async (prompt: string) => {
    setIsGenerating(true)
    await new Promise((resolve) => setTimeout(resolve, 600))

    const reply: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: buildReply(prompt),
    }

    setMessages((prev) => [...prev, reply])
    setIsGenerating(false)
  }

  const handleSubmit = (event?: { preventDefault?: () => void }) => {
    event?.preventDefault?.()
    const trimmed = input.trim()

    if (!trimmed || isGenerating) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    void respond(trimmed)
  }

  return (
    <main
      className="dark relative h-[100dvh] overflow-hidden bg-[#090909] text-white"
      style={{
        "--background": "#090909",
        "--foreground": "#f5f5f5",
        "--primary": "#e5e5e5",
        "--primary-foreground": "#111111",
        "--muted": "#242424",
        "--muted-foreground": "#a3a3a3",
        "--border": "#272727",
        "--input": "#272727",
      } as React.CSSProperties}
    >
      <header className="absolute inset-x-0 top-0 z-10 flex h-14 items-center justify-between px-4 sm:px-6">
        <a
          href="/"
          className="rounded-md bg-[#242424] px-3 py-2 text-sm text-white transition-colors hover:bg-[#303030]"
        >
          &larr; Back to site
        </a>
        <button
          type="button"
          className="flex h-10 items-center gap-5 rounded-md border border-[#292929] bg-[#090909] px-3 text-sm text-white transition-colors hover:bg-[#141414]"
          aria-label="Selected model: Northstar AI"
        >
          Northstar AI
          <ChevronDown className="h-4 w-4 text-neutral-400" />
        </button>
      </header>

      <div className="mx-auto h-full w-full max-w-4xl px-4 pb-6 pt-20 sm:px-0 sm:pt-3">
        <Chat
          messages={messages}
          input={input}
          handleInputChange={(event) => setInput(event.target.value)}
          handleSubmit={handleSubmit}
          append={append}
          suggestions={suggestions}
          isGenerating={isGenerating}
          stop={() => setIsGenerating(false)}
          className="h-full min-h-0"
        />
      </div>
    </main>
  )
}