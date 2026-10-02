import { DiscordEmbed, colorToHex } from "@/lib/discord-embed";
import { cn } from "@/lib/utils";

interface DiscordEmbedPreviewProps {
  username?: string;
  embed: DiscordEmbed | null;
  plainContent?: string | null;
  format?: "plain" | "embed";
  className?: string;
}

export function DiscordEmbedPreview({
  username = "HomeLab DNS",
  embed,
  plainContent,
  format = "embed",
  className,
}: DiscordEmbedPreviewProps) {
  const accent = colorToHex(embed?.color);

  return (
    <div
      className={cn(
        "rounded-lg border border-[#1e1f22] bg-[#313338] p-4 text-[15px] text-[#dbdee1] shadow-lg",
        className
      )}
    >
      <div className="flex gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#5865F2] text-sm font-bold text-white">
          HD
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-medium text-white">{username || "HomeLab DNS"}</span>
            <span className="rounded bg-[#5865F2] px-1 py-0.5 text-[10px] font-semibold uppercase text-white">
              App
            </span>
            <span className="text-xs text-[#949ba4]">Today at {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
          </div>

          {format === "plain" && plainContent && (
            <p className="whitespace-pre-wrap break-words leading-snug">{plainContent}</p>
          )}

          {format === "embed" && embed && (
            <div className="mt-1 flex max-w-lg overflow-hidden rounded">
              <div className="w-1 shrink-0" style={{ backgroundColor: accent }} />
              <div className="flex-1 space-y-2 bg-[#2b2d31] px-3 py-2">
                {embed.title && <p className="font-semibold text-white">{embed.title}</p>}
                {embed.description && (
                  <p className="whitespace-pre-wrap break-words text-sm leading-snug text-[#dbdee1]">
                    {embed.description}
                  </p>
                )}
                {embed.fields && embed.fields.length > 0 && (
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    {embed.fields.map((f, i) => (
                      <div key={`${f.name}-${i}`} className={f.inline === false ? "col-span-2" : ""}>
                        <p className="text-xs font-semibold text-white">{f.name}</p>
                        <p className="break-words text-sm text-[#dbdee1]">{f.value}</p>
                      </div>
                    ))}
                  </div>
                )}
                {embed.footer?.text && (
                  <p className="pt-1 text-xs text-[#949ba4]">{embed.footer.text}</p>
                )}
              </div>
            </div>
          )}

          {format === "embed" && !embed && (
            <p className="text-sm text-[#949ba4]">No embed preview available for this event.</p>
          )}
        </div>
      </div>
    </div>
  );
}
