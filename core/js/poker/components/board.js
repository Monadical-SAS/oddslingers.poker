import React from 'react'


export const DealerButtonComponent = ({btn_coord, style}) => {
    const coord = btn_coord || {}
    const stylez = style || {}
    return (btn_coord || style) ? <div className="dealbtn"
         style={{
            width: `${coord.width}px`,
            height: `${coord.height}px`,
            top: `${coord.top}px`,
            left: `${coord.left}px`,
            position: 'absolute',
            display: 'inline-block',
            zIndex: 35,
            margin: 0,
            ...stylez,
        }}> D
    </div> : <div id='none'/>
}

export const DealerIcon = ({style}) =>
    <DealerButtonComponent style={{
        height: 20,
        width: 20,
        position: 'initial',
        fontSize: '88%',
        ...style
    }}/>
