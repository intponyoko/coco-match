type SubmissionProgressProps = {
  title: string;
  body: string;
};

export default function SubmissionProgress({
  title,
  body,
}: SubmissionProgressProps) {
  return (
    <section className="submission-progress" aria-live="polite" aria-busy="true">
      <div className="submission-progress-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div>
        <strong>{title}</strong>
        <p>{body}</p>
      </div>
    </section>
  );
}
