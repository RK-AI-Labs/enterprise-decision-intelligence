import { Sparkles } from "lucide-react"

interface PromptSuggestionsProps {
  label: string
  append: (message: { role: "user"; content: string }) => void
  suggestions: string[]
}

export function PromptSuggestions({
  label,
  append,
  suggestions,
}: PromptSuggestionsProps) {
  return (
    <div className="space-y-6">
      <h2 className="flex items-center justify-center gap-2 text-center text-2xl font-bold text-foreground">
        {label}
        <Sparkles className="h-5 w-5" aria-hidden="true" />
      </h2>
      <div className="grid gap-3 text-sm sm:grid-cols-3 sm:gap-6">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => append({ role: "user", content: suggestion })}
            className="flex h-max min-h-14 self-start items-center justify-center rounded-lg border border-[#262626] bg-[#090909] p-4 text-center text-foreground transition-colors hover:bg-[#141414]"
          >
            <p>{suggestion}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
