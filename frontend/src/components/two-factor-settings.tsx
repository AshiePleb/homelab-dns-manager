import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/auth";
import { api } from "@/lib/api";

export function TwoFactorSettings({ onMessage }: { onMessage: (msg: string) => void }) {
  const { user, refreshUser } = useAuth();
  const [totpSetup, setTotpSetup] = useState<{ secret: string; provisioning_uri: string } | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");

  const start2fa = async () => {
    try {
      const setup = await api.setup2FA();
      setTotpSetup(setup);
      onMessage("Scan the URI in your authenticator app, then enter the code below");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "2FA setup failed");
    }
  };

  const enable2fa = async () => {
    try {
      await api.enable2FA(totpCode);
      setTotpSetup(null);
      setTotpCode("");
      await refreshUser();
      onMessage("Two-factor authentication enabled");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Invalid code");
    }
  };

  const disable2fa = async () => {
    try {
      await api.disable2FA(disableCode, disablePassword);
      setDisableCode("");
      setDisablePassword("");
      await refreshUser();
      onMessage("Two-factor authentication disabled");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Could not disable 2FA");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Two-factor authentication (2FA)</CardTitle>
        <CardDescription>
          {user?.totp_enabled
            ? "Authenticator app is required when signing in"
            : "Add a TOTP code from Google Authenticator, 1Password, etc."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!user?.totp_enabled && !totpSetup && (
          <Button type="button" variant="outline" onClick={start2fa}>
            Set up 2FA
          </Button>
        )}

        {totpSetup && (
          <div className="space-y-3 rounded-md border border-border p-4 text-sm">
            <p className="font-medium">Add this account to your authenticator</p>
            <p className="text-xs text-muted-foreground break-all font-mono bg-secondary/50 p-2 rounded">
              {totpSetup.provisioning_uri}
            </p>
            <p className="text-xs text-muted-foreground">Manual secret: {totpSetup.secret}</p>
            <div className="space-y-2 max-w-xs">
              <Label htmlFor="totp-enable">Verification code</Label>
              <Input
                id="totp-enable"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="000000"
              />
            </div>
            <Button type="button" onClick={enable2fa} disabled={totpCode.length < 6}>
              Enable 2FA
            </Button>
          </div>
        )}

        {user?.totp_enabled && (
          <div className="space-y-3 max-w-md">
            <div className="space-y-2">
              <Label htmlFor="totp-disable-code">Authenticator code</Label>
              <Input
                id="totp-disable-code"
                inputMode="numeric"
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="totp-disable-pass">Current password</Label>
              <Input
                id="totp-disable-pass"
                type="password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
              />
            </div>
            <Button type="button" variant="destructive" onClick={disable2fa}>
              Disable 2FA
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
