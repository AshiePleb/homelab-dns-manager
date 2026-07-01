import { useState } from "react";
import { ThemePicker } from "@/components/theme-picker";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { usePreferences } from "@/context/theme";

export function AppearanceSettings({ onMessage }: { onMessage: (msg: string) => void }) {
  const { preferences, updatePreferences } = usePreferences();
  const [saving, setSaving] = useState(false);

  const saveAccessibility = async () => {
    setSaving(true);
    try {
      await updatePreferences({
        font_size: preferences.font_size,
        reduce_motion: preferences.reduce_motion,
        colorblind_mode: preferences.colorblind_mode,
      });
      onMessage("Appearance settings saved");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Theme</CardTitle>
          <CardDescription>
            Per-user appearance — saved to your account and this browser. Includes standard and accessibility themes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ThemePicker />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Accessibility</CardTitle>
          <CardDescription>Adjust readability and motion independent of your chosen theme</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="font-size">Font size — {preferences.font_size}%</Label>
              <span className="text-xs text-muted-foreground">90% – 130%</span>
            </div>
            <input
              id="font-size"
              type="range"
              min={90}
              max={130}
              step={5}
              value={preferences.font_size}
              onChange={(e) => void updatePreferences({ font_size: Number(e.target.value) })}
              className="w-full accent-primary"
              aria-valuemin={90}
              aria-valuemax={130}
              aria-valuenow={preferences.font_size}
            />
          </div>

          <label className="flex items-start gap-3 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="mt-1"
              checked={preferences.reduce_motion}
              onChange={(e) => void updatePreferences({ reduce_motion: e.target.checked })}
            />
            <span>
              <span className="font-medium block">Reduce motion</span>
              <span className="text-muted-foreground text-xs">
                Minimizes animations even if your OS allows motion
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="mt-1"
              checked={preferences.colorblind_mode}
              onChange={(e) => void updatePreferences({ colorblind_mode: e.target.checked })}
            />
            <span>
              <span className="font-medium block">Color-blind safe status</span>
              <span className="text-muted-foreground text-xs">
                Uses icons and patterns on status indicators — not color alone
              </span>
            </span>
          </label>

          <Button type="button" onClick={saveAccessibility} disabled={saving}>
            {saving ? "Saving…" : "Save accessibility options"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
