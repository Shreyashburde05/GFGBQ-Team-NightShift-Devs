import { useState, useCallback } from "react";
import { Claim, Citation } from "@/components/AnalysisResults";
import { toast } from "@/hooks/use-toast";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/verify";

export const useVerification = () => {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [overallScore, setOverallScore] = useState(0);
  const [hasResults, setHasResults] = useState(false);

  const analyzeText = useCallback(async (text: string) => {
    if (!text.trim()) {
      toast({
        title: "Empty Text",
        description: "Please provide some text to analyze.",
        variant: "destructive",
      });
      return;
    }

    setIsAnalyzing(true);
    setHasResults(true);
    setClaims([]);
    setCitations([]);
    setOverallScore(0);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to verify content");
      }

      const data = await response.json();
      
      setClaims(data.claims);
      setCitations(data.citations);
      setOverallScore(data.overallScore);
    } catch (error: any) {
      console.error("Verification error:", error);
      toast({
        title: "Verification Failed",
        description: error.message || "Could not connect to the verification server.",
        variant: "destructive",
      });
      setHasResults(false);
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  return {
    claims,
    citations,
    isAnalyzing,
    overallScore,
    hasResults,
    analyzeText,
  };
};
