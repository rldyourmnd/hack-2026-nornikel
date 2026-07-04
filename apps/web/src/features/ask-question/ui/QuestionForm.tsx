import { Search } from "lucide-react";

type QuestionFormProps = {
  disabled?: boolean;
  question: string;
  onQuestionChange: (question: string) => void;
  onSubmit: (question: string) => void;
};

export function QuestionForm({
  disabled,
  question,
  onQuestionChange,
  onSubmit,
}: QuestionFormProps) {
  return (
    <form
      className="question-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(question);
      }}
    >
      <textarea
        aria-label="Вопрос по материалу, режиму и свойству"
        placeholder="Например: выполнить литературный обзор методов очистки шахтных вод цветной металлургии..."
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
      />
      <div className="button-row">
        <button className="primary-button" disabled={disabled} type="submit">
          <Search size={17} />
          Найти доказательства
        </button>
      </div>
    </form>
  );
}
