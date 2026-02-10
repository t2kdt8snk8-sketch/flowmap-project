const MOCK_STEP_PROMPTS = [
    // Step 01
    {
        id: "prompt_0101",
        step_id: "step_01",
        prompt_text: "이 문제의 가장 근본적인 원인은 무엇인가요?",
        prompt_type: "분석형",
        order_index: 0
    },
    {
        id: "prompt_0102",
        step_id: "step_01",
        prompt_text: "이 주제와 관련하여 놓치고 있는 배경 정보가 있나요?",
        prompt_type: "구조화",
        order_index: 1
    },
    {
        id: "prompt_0103",
        step_id: "step_01",
        prompt_text: "해결하고자 하는 핵심 목표를 한 문장으로 정의해 보세요.",
        prompt_type: "구조화",
        order_index: 2
    },

    // Step 02
    {
        id: "prompt_0201",
        step_id: "step_02",
        prompt_text: "기존의 방식과 완전히 반대로 생각한다면 어떨까요?",
        prompt_type: "확장형",
        order_index: 0
    },
    {
        id: "prompt_0202",
        step_id: "step_02",
        prompt_text: "다른 산업이나 분야에서 차용할 수 있는 아이디어가 있나요?",
        prompt_type: "연결형",
        order_index: 1
    },
    {
        id: "prompt_0203",
        step_id: "step_02",
        prompt_text: "제약 조건이 없다면 어떤 시도를 해보고 싶나요?",
        prompt_type: "확장형",
        order_index: 2
    },

    // Step 03
    {
        id: "prompt_0301",
        step_id: "step_03",
        prompt_text: "가장 적은 리소스로 가장 큰 효과를 낼 수 있는 방법은 무엇인가요?",
        prompt_type: "분석형",
        order_index: 0
    },
    {
        id: "prompt_0302",
        step_id: "step_03",
        prompt_text: "지금 당장 실행 가능한 가장 구체적인 안은 무엇인가요?",
        prompt_type: "분석형",
        order_index: 1
    },
    {
        id: "prompt_0303",
        step_id: "step_03",
        prompt_text: "이 선택을 했을 때 예상되는 가장 큰 리스크는 무엇인가요?",
        prompt_type: "분석형",
        order_index: 2
    },

    // Step 04
    {
        id: "prompt_0401",
        step_id: "step_04",
        prompt_text: "내일 당장 시작해야 할 첫 번째 행동은 무엇인가요?",
        prompt_type: "연결형",
        order_index: 0
    },
    {
        id: "prompt_0402",
        step_id: "step_04",
        prompt_text: "성공 여부를 판단할 수 있는 지표는 무엇인가요?",
        prompt_type: "구조화",
        order_index: 1
    },
    {
        id: "prompt_0403",
        step_id: "step_04",
        prompt_text: "지속적인 실행을 위해 어떤 루틴이 필요한가요?",
        prompt_type: "연결형",
        order_index: 2
    }
];
