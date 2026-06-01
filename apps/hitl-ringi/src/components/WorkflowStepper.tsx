import StatusBadge from "./StatusBadge";

type WorkflowStepperProps = {
  steps: { label: string; status: string; count?: number }[];
};

export default function WorkflowStepper({ steps }: WorkflowStepperProps) {
  return (
    <ol className="workflow-stepper" aria-label="Workflow progress">
      {steps.map((step) => (
        <li className="workflow-step" key={step.label}>
          <div className="workflow-step-title">{step.label}</div>
          <StatusBadge status={step.status} />
          {step.count !== undefined ? <div className="muted">{step.count.toLocaleString()} 件</div> : null}
        </li>
      ))}
    </ol>
  );
}
