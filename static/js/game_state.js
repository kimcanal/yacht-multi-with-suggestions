/**
 * static/js/game_state.js
 * 클라이언트 게임 상태 저장소
 */

const GameState = (() => {
    let state = {
        dice: [1, 1, 1, 1, 1],
        kept: [0, 0, 0, 0, 0],
        rollsLeft: 3,
        myCard: Array(12).fill(null),
        oppCard: Array(12).fill(null),
        gameOver: false,
        aiRec: null
    };

    return {
        getDice: () => [...state.dice],
        setDice: (value) => { state.dice = [...value]; },
        getKept: () => [...state.kept],
        setKept: (value) => { state.kept = [...value]; },
        getRollsLeft: () => state.rollsLeft,
        setRollsLeft: (value) => { state.rollsLeft = value; },
        getMyCard: () => [...state.myCard],
        setMyCard: (value) => { state.myCard = [...value]; },
        getOppCard: () => [...state.oppCard],
        setOppCard: (value) => { state.oppCard = [...value]; },
        isGameOver: () => state.gameOver,
        setGameOver: (value) => { state.gameOver = value; },
        getAiRec: () => state.aiRec,
        setAiRec: (value) => { state.aiRec = value; },
        getState: () => ({ ...state }),
        setState: (newState) => { state = { ...state, ...newState }; }
    };
})();
