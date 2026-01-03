import { useState, useCallback } from "react";
import { Claim, Citation } from "@/components/AnalysisResults";
import { VerificationStatus } from "@/components/ClaimCard";

// Simulated verification - in production, this would call your backend API
const simulateClaimExtraction = (text: string): Claim[] => {
  // Simple heuristic claim detection
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [];
  const claims: Claim[] = [];

  sentences.forEach((sentence, index) => {
    // Detect claims with numbers, dates, or research-related keywords
    const hasNumbers = /\d+/.test(sentence);
    const hasResearchKeywords = /study|research|found|according|published|report/i.test(sentence);
    
    if (hasNumbers || hasResearchKeywords) {
      claims.push({
        id: `claim-${index}`,
        text: sentence.trim(),
        status: "pending" as VerificationStatus,
        confidence: 0,
      });
    }
  });

  return claims;
};

const simulateCitationExtraction = (text: string): Citation[] => {
  const citations: Citation[] = [];
  
  // Look for paper titles in quotes
  const quotedMatches = text.match(/"[^"]+"/g) || [];
  quotedMatches.forEach((match, index) => {
    if (match.length > 20) {
      citations.push({
        id: `citation-${index}`,
        text: match.replace(/"/g, ""),
        exists: null,
        checkingStatus: "pending",
      });
    }
  });

  // Look for journal names
  const journalKeywords = ["Nature", "Science", "Journal", "Review", "Proceedings"];
  journalKeywords.forEach((keyword, index) => {
    if (text.includes(keyword)) {
      const surroundingText = text.substring(
        Math.max(0, text.indexOf(keyword) - 20),
        text.indexOf(keyword) + keyword.length + 30
      );
      citations.push({
        id: `citation-journal-${index}`,
        text: surroundingText.trim(),
        exists: null,
        checkingStatus: "pending",
      });
    }
  });

  return citations;
};

const simulateVerification = async (
  claim: Claim,
  delay: number
): Promise<Claim> => {
  await new Promise((resolve) => setTimeout(resolve, delay));

  // Simulate verification results based on claim content
  const statuses: VerificationStatus[] = ["verified", "uncertain", "hallucinated"];
  const randomIndex = Math.random();
  
  let status: VerificationStatus;
  let confidence: number;
  let source: string | undefined;
  let sourceUrl: string | undefined;
  let explanation: string | undefined;

  // Bias results based on content
  if (claim.text.toLowerCase().includes("3.5°c") || claim.text.toLowerCase().includes("78%")) {
    // These are fake stats in our example
    status = "hallucinated";
    confidence = Math.floor(Math.random() * 20) + 75;
    explanation = "This statistic could not be verified in any reputable scientific database.";
  } else if (claim.text.toLowerCase().includes("mit") || claim.text.toLowerCase().includes("nature")) {
    status = "uncertain";
    confidence = Math.floor(Math.random() * 30) + 40;
    explanation = "Source institution mentioned but specific claim details couldn't be fully verified.";
    source = "Partial match found";
  } else if (randomIndex > 0.6) {
    status = "verified";
    confidence = Math.floor(Math.random() * 15) + 85;
    source = "Wikipedia";
    sourceUrl = "https://wikipedia.org";
    explanation = "Claim verified against multiple reliable sources.";
  } else if (randomIndex > 0.3) {
    status = "uncertain";
    confidence = Math.floor(Math.random() * 30) + 40;
    explanation = "Mixed results from source verification.";
  } else {
    status = "hallucinated";
    confidence = Math.floor(Math.random() * 25) + 70;
    explanation = "No supporting evidence found for this claim.";
  }

  return {
    ...claim,
    status,
    confidence,
    source,
    sourceUrl,
    explanation,
  };
};

const simulateCitationCheck = async (
  citation: Citation,
  delay: number
): Promise<Citation> => {
  await new Promise((resolve) => setTimeout(resolve, delay));

  // Simulate citation verification
  const exists = Math.random() > 0.6;
  
  return {
    ...citation,
    exists,
    url: exists ? "https://scholar.google.com" : undefined,
    checkingStatus: "complete" as const,
  };
};

export const useVerification = () => {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [overallScore, setOverallScore] = useState(0);
  const [hasResults, setHasResults] = useState(false);

  const analyzeText = useCallback(async (text: string) => {
    setIsAnalyzing(true);
    setHasResults(true);
    setOverallScore(0);

    // Extract claims and citations
    const extractedClaims = simulateClaimExtraction(text);
    const extractedCitations = simulateCitationExtraction(text);

    setClaims(extractedClaims);
    setCitations(extractedCitations);

    // Verify claims with staggered delays
    const verifiedClaims = await Promise.all(
      extractedClaims.map((claim, index) =>
        simulateVerification(claim, (index + 1) * 800)
      )
    );

    setClaims(verifiedClaims);

    // Check citations
    const checkedCitations = await Promise.all(
      extractedCitations.map((citation, index) =>
        simulateCitationCheck(citation, (index + 1) * 600 + 1000)
      )
    );

    setCitations(checkedCitations);

    // Calculate overall score
    const verifiedCount = verifiedClaims.filter(
      (c) => c.status === "verified"
    ).length;
    const validCitations = checkedCitations.filter((c) => c.exists).length;

    const claimScore = extractedClaims.length > 0
      ? (verifiedCount / extractedClaims.length) * 60
      : 60;
    const citationScore = extractedCitations.length > 0
      ? (validCitations / extractedCitations.length) * 40
      : 40;

    setOverallScore(Math.round(claimScore + citationScore));
    setIsAnalyzing(false);
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
