from typing import Generic, TypeVar

from cocom.pipeline.common.io import PipelinePayload
from cocom.pipeline.common.paths import PipelinePaths


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class StatelessPipeline(Generic[InputT, OutputT]):
    name: str = "stateless_pipeline"

    def run(self, pipeline_input: InputT) -> OutputT:
        raise NotImplementedError(f"{self.__class__.__name__}.run is not implemented")

    def input_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> InputT:
        raise NotImplementedError(
            f"{self.__class__.__name__}.input_from_payload is not implemented"
        )

    def output_to_payload(
        self,
        output: OutputT,
        base: PipelinePayload,
    ) -> PipelinePayload:
        raise NotImplementedError(
            f"{self.__class__.__name__}.output_to_payload is not implemented"
        )

    def run_from_payload(
        self,
        payload: PipelinePayload,
        paths: PipelinePaths | None = None,
    ) -> PipelinePayload:
        pipeline_input = self.input_from_payload(payload, paths)
        output = self.run(pipeline_input)
        return self.output_to_payload(output, payload)

    def load_payload(self, paths: PipelinePaths | None = None) -> PipelinePayload:
        raise NotImplementedError(
            f"{self.__class__.__name__}.load_payload is not implemented"
        )

    def write_output(
        self,
        output: OutputT,
        paths: PipelinePaths | None = None,
    ) -> None:
        raise NotImplementedError(
            f"{self.__class__.__name__}.write_output is not implemented"
        )

    def main(self) -> None:
        raise NotImplementedError(f"{self.__class__.__name__}.main is not implemented")

