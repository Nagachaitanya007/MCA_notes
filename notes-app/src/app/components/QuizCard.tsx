'use client';

import { useState } from 'react';

interface QuizQuestion {
  id: number;
  scenario: string;
  question: string;
  options: string[];
  correct_answer_letter: string;
  correct_answer_text: string;
  explanation: string;
}

interface QuizData {
  date: string;
  topic: string;
  questions: QuizQuestion[];
}

export default function QuizCard({ quiz, startNumber = 1 }: { quiz: QuizData; startNumber?: number }) {
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});

  const selectAnswer = (questionId: number, letter: string) => {
    if (revealed[questionId]) return; // Already revealed
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: letter }));
  };

  const revealAnswer = (questionId: number) => {
    setRevealed((prev) => ({ ...prev, [questionId]: true }));
  };

  return (
    <div className="bg-gray-900/50 border border-gray-800/60 rounded-xl overflow-hidden shadow-xl shadow-indigo-500/5">
      {/* Quiz Header */}
      <div className="px-4 sm:px-6 py-5 border-b border-gray-800/60 flex justify-between items-center bg-gray-900/30">
        <div>
          <h3 className="text-sm sm:text-base font-bold text-white tracking-tight">{quiz.topic}</h3>
          <p className="text-[10px] sm:text-xs text-indigo-400/70 font-medium uppercase tracking-widest mt-1">
            {new Date(quiz.date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
          </p>
        </div>
        <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full">
          <span className="text-[10px] sm:text-xs text-indigo-400 font-semibold">{quiz.questions.length} Questions</span>
        </div>
      </div>

      {/* Questions */}
      <div className="divide-y divide-gray-800/40">
        {quiz.questions.map((q, idx) => {
          const isRevealed = revealed[q.id];
          const userAnswer = selectedAnswers[q.id];
          const isCorrect = userAnswer === q.correct_answer_letter;
          const displayId = startNumber + idx;

          return (
            <div key={q.id} className="px-4 sm:px-6 py-8">
              {/* Scenario */}
              <div className="bg-gray-900/30 border-l-2 border-indigo-500/30 p-4 rounded-r-lg mb-6">
                <p className="text-xs sm:text-sm text-gray-400 italic leading-relaxed">{q.scenario}</p>
              </div>

              {/* Question */}
              <p className="text-sm sm:text-base font-bold text-gray-100 mb-6 leading-snug flex items-start">
                <span className="text-indigo-500 mr-3">Q{displayId}.</span>
                {q.question}
              </p>

              {/* Options */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
                {q.options.map((opt) => {
                  const letter = opt.charAt(0);
                  const isSelected = userAnswer === letter;
                  const isCorrectOption = q.correct_answer_letter === letter;

                  let optionStyle = 'bg-gray-800/30 border-gray-800/50 text-gray-400 hover:border-indigo-500/50 cursor-pointer';
                  if (isRevealed) {
                    if (isCorrectOption) {
                      optionStyle = 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400 ring-1 ring-emerald-500/20';
                    } else if (isSelected && !isCorrect) {
                      optionStyle = 'bg-red-500/10 border-red-500/40 text-red-400 ring-1 ring-red-500/20';
                    } else {
                      optionStyle = 'bg-gray-900/40 border-gray-900 text-gray-600 opacity-50';
                    }
                  } else if (isSelected) {
                    optionStyle = 'bg-indigo-500/10 border-indigo-500/50 text-indigo-300 ring-1 ring-indigo-500/30 shadow-md shadow-indigo-500/10';
                  }

                  return (
                    <button
                      key={opt}
                      onClick={() => selectAnswer(q.id, letter)}
                      disabled={isRevealed}
                      className={`w-full text-left px-5 py-3 rounded-xl border text-xs sm:text-sm transition-all duration-300 ${optionStyle}`}
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>

              {/* Reveal / Result */}
              {!isRevealed ? (
                <button
                  onClick={() => revealAnswer(q.id)}
                  disabled={!userAnswer}
                  className="w-full sm:w-auto px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 text-white text-xs font-bold rounded-lg transition-all shadow-lg shadow-indigo-600/20 disabled:shadow-none disabled:text-gray-500 cursor-pointer disabled:cursor-not-allowed"
                >
                  {userAnswer ? 'Check Answer →' : 'Select an option to continue'}
                </button>
              ) : (
                <div className={`mt-4 p-5 rounded-xl border-2 ${isCorrect ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-red-500/5 border-red-500/20'}`}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`text-lg ${isCorrect ? 'text-emerald-400' : 'text-red-400'}`}>
                      {isCorrect ? '✓' : '✗'}
                    </span>
                    <p className={`font-bold text-sm sm:text-base ${isCorrect ? 'text-emerald-400' : 'text-red-400'}`}>
                      {isCorrect ? 'Perfectly Correct!' : `Not quite — The answer is ${q.correct_answer_text}`}
                    </p>
                  </div>
                  <div className="bg-black/20 p-4 rounded-lg">
                    <p className="text-gray-300 text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-medium">
                      <span className="text-indigo-400 font-bold block mb-1 uppercase text-[10px] tracking-wider">Expert Deep Dive:</span>
                      {q.explanation}
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
