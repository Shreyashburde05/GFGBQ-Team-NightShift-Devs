import { Shield, Github } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Header = () => {
  return (
    <header className="border-b border-border/50 bg-background/80 backdrop-blur-xl sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/30 blur-xl rounded-full" />
              <div className="relative w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 overflow-hidden">
                <img src="/logo.png" alt="TrustGuard Logo" className="w-full h-full object-cover" />
              </div>
            </div>
            <div>
              <h1 className="font-mono font-bold text-xl text-foreground tracking-tight">
                TrustGuard
                <span className="text-primary">AI</span>
              </h1>
              <p className="text-xs text-muted-foreground font-mono">
                AI Hallucination Detector
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="glass" size="sm" className="font-mono gap-2">
              <Github className="w-4 h-4" />
              <span className="hidden sm:inline">Source</span>
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
};
