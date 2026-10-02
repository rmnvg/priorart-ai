import type { InterviewPlan } from "@/types/analysis";

export const MAX_IDEA_LENGTH = 6000;

/** Only inventor-written answers enter the search. No generated paraphrase,
 * default mechanism, or unanswered question becomes part of the invention. */
export function interviewDescription(idea: string, plan: InterviewPlan, answers: string[]): string {
  const answered = plan.questions.flatMap((q, index) => {
    const answer = answers[index]?.trim();
    return answer ? [`Question (context only): ${q.question}\nInventor's answer: ${answer}`] : [];
  });
  return [idea.trim(), ...answered].join("\n\n");
}
