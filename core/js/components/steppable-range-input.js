import React from 'react'

import noUiSlider from 'nouislider'


export class SteppableRangeInput extends React.Component {
    constructor(props){
        super(props)
        this.state = {
            initialized: false,
            width: 340,
        }
    }
    get_range(marks, step) {
        const range = {}
        const length = marks.length
        const distance = 100/ (length - 1)

        range.min = [marks[0].amt, step]

        for (let idx in marks.slice(1, length - 1)) {
            idx = parseInt(idx)
            const key = `${distance*(idx + 1)}%`
            range[key] = [marks[idx + 1].amt, step]
        }
        range.max = [marks[length - 1].amt, step]

        return range

    }
    componentDidMount() {
        const {onChange, marks, value} = this.props
        const step = 1
        const nonLinearSlider = document.getElementById('slider')

        noUiSlider.create(nonLinearSlider, {
            start: [value],
            range: marks ? this.get_range(marks, step) : {},
            pips: marks ? {
                mode: 'range',
                density: 3,
                format: {
                    to: (value) => {
                        for (let mark of Object.values(marks)) {
                            if (value === mark.amt) {
                                return `${mark.label} ${ mark.str ?  `(${mark.str})` :'' }`
                            }
                        }
                    }
                }
            } : {}
        })
        nonLinearSlider.noUiSlider.on('update',
            (values, handle) => onChange(values[handle])
        )

        setTimeout(() => {
            $("div.noUi-value.noUi-value-horizontal").click(function() {
                const text = $(this).text()
                const start = text.indexOf('(') + 1
                if (start !== 0) {
                    const value_str = text.substr(start)
                    const value = value_str.replace(')', '')
                    for (let mark of Object.values(marks)) {
                        if (value === mark.str) {
                            nonLinearSlider.noUiSlider.set(mark.amt)
                            break
                        }
                    }
                } else {
                    nonLinearSlider.noUiSlider.set(text)
                }
            })
        }, 500)
    }
    shouldComponentUpdate(nextProps) {
        if (this.props.value != nextProps.value){
            const bets = this.props.marks.map(bet => bet.amt)
            if (bets.includes(nextProps.value)){
                const nonLinearSlider = document.getElementById('slider')
                if (!(nonLinearSlider.noUiSlider.get().includes(nextProps.value))){
                    nonLinearSlider.noUiSlider.set([nextProps.value])
                }
            }
        }
        return false;
    }
    render() {
        return <div className="slider-row">
            <div id="slider">
            </div>
        </div>
    }
}
