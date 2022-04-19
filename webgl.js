var flareColors = [
    "hsl(170, 100%, 20%)",
];

// var background = document.getElementById("background");
// var flares = background.getElementsByClassName("flare");
// var flareSize = background.clientWidth * 0.8;
// var height = background.clientHeight + flareSize * 1;
// var width = background.clientWidth + flareSize * 1;

// var frameCount = 10;
// var durationMin = 50000;
// var durationMax = 70000;

// var perimeter = width*2 + height*2;

// for(var i=0; i<flares.length; i++){  
//     flares[i].style.setProperty("box-shadow", "0 "+flareSize*2+"px "+flareSize*0.5+"px " + flareColors[i % flareColors.length]);
//     let frames = [];
//     let rand = Math.random()*perimeter;
//     for(var j=0; j<frameCount; j++){
//         rand = (rand + (Math.random()*0.33 + 0.33)*perimeter) % perimeter;
//         let x = -flareSize*1.0;
//         let y = -flareSize*3.0;
//         if(rand < width){
//             x += rand;
//             y += 0;
//         }else if(rand < width + height){
//             x += width;
//             y += rand - width;
//         }else if(rand < width*2 + height){
//             x += width - (rand - width - height);
//             y += height;
//         }else{
//             x += 0;
//             y += height - (rand - width*2 - height);
//         }

//         frames.push({transform: 'translate('+ x +'px,'+ y +'px)'});
//     }
//     frames.push(frames[0]);

//     let effect = new KeyframeEffect(
//         flares[i],
//         frames,
//         {
//             duration: durationMin + Math.random()*(durationMax - durationMin), 
//             easing: "linear" ,
//             iterations: Infinity
//         }
//     );

//     let animation = new Animation(effect);
//     //animation.currentTime = 0;
//     animation.currentTime = Math.random()*(durationMax);
//     animation.play();
// }



var gl = null;
        var glCanvas = null;

        var buffer = windowWidth * 0.1;

        var flareRad = 60;
        var speed = 120.0;
        var flarePos = [];
        var flareVel = [];
        var deviation = windowWidth * 80;
        var flareCol = [];
        var flareCount = 5;

        for (let i = 0; i < flareCount; i++) {
            flarePos.push([Math.random() * (windowWidth + (buffer * 2)) - buffer, Math.random() * (windowHeight + (buffer * 2)) - buffer]);
            let rot = Math.random() * 2 * Math.PI;
            flareVel.push([Math.cos(rot) * speed, Math.sin(rot) * speed]);

            flareCol.push([]);
            for (let j = 0; j < flareCount; j++) {
                flareCol[i].push(false);
            }
        }

        for (var i = 0; i < flareCount - 1; i++) {

            for (var j = i + 1; j < flareCount; j++) {
                let diffPos = [flarePos[i][0] - flarePos[j][0], flarePos[i][1] - flarePos[j][1]];
                let distance = Math.pow(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1], 0.5);

                if (distance < flareRad * 2) {
                    flareCol[i][j] = true;
                } else {
                    flareCol[i][j] = false;
                }
            }
        }

        let vertexCount;

        let uScalingFactor;
        let uColorBase;
        let uColorPoint;
        let uDeviation;
        let uPoint0;
        let uPoint1;
        let uPoint2;
        let uPoint3;
        let uPoint4;
        let uPoint5;
        let uPoint6;
        let uPoint7;

        let prevTime = 0.0;

        var shaderProgram = null;

        //window.addEventListener("load", startup, false);

        function startup() {
            glCanvas = document.getElementById("glcanvas");
            glCanvas.setAttribute("width", glCanvas.clientWidth);
            glCanvas.setAttribute("height", glCanvas.clientHeight);
            gl = glCanvas.getContext("webgl2");

            const shaderSet = [
                {
                    type: gl.VERTEX_SHADER,
                    id: "vertex-shader"
                },
                {
                    type: gl.FRAGMENT_SHADER,
                    id: "fragment-shader"
                }
            ];

            shaderProgram = buildShaderProgram(shaderSet);

            let ratio = glCanvas.height / glCanvas.width;

            let vertexArray = new Float32Array([
                -1, -ratio, -1, ratio, 1, -ratio, 1, ratio
            ]);

            let vertexBuffer = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
            gl.bufferData(gl.ARRAY_BUFFER, vertexArray, gl.STATIC_DRAW);

            let vertexNumComponents = 2;
            vertexCount = vertexArray.length / vertexNumComponents;

            gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);

            let aVertexPosition = gl.getAttribLocation(shaderProgram, "aVertexPosition");

            gl.enableVertexAttribArray(aVertexPosition);
            gl.vertexAttribPointer(aVertexPosition, vertexNumComponents, gl.FLOAT, false, 0, 0);

            gl.viewport(0, 0, glCanvas.width, glCanvas.height);

            gl.useProgram(shaderProgram);

            uScalingFactor = gl.getUniformLocation(shaderProgram, "uScalingFactor");

            uColorBase = gl.getUniformLocation(shaderProgram, "uColorBase");
            uColorPoint = gl.getUniformLocation(shaderProgram, "uColorPoint");

            uDeviation = gl.getUniformLocation(shaderProgram, "uDeviation");

            uPoint0 = gl.getUniformLocation(shaderProgram, "uPoint0");
            uPoint1 = gl.getUniformLocation(shaderProgram, "uPoint1");
            uPoint2 = gl.getUniformLocation(shaderProgram, "uPoint2");
            uPoint3 = gl.getUniformLocation(shaderProgram, "uPoint3");
            uPoint4 = gl.getUniformLocation(shaderProgram, "uPoint4");
            uPoint5 = gl.getUniformLocation(shaderProgram, "uPoint5");
            uPoint6 = gl.getUniformLocation(shaderProgram, "uPoint6");
            uPoint7 = gl.getUniformLocation(shaderProgram, "uPoint7");
            
            gl.uniform2fv(uScalingFactor, [1.0, windowWidth/windowHeight]);

            // gl.uniform4fv(uColorBase, [0, 0, 0, 1]);
            // gl.uniform4fv(uColorPoint, [1, 1, 1, 1]);

            gl.uniform4fv(uColorBase, [0.4, 0, 0.267, 1.0]);
            gl.uniform4fv(uColorPoint, [0, 0.4, 0.333, 1.0]);

            gl.uniform1f(uDeviation, deviation);
        }

        function buildShaderProgram(shaderInfo) {
            let program = gl.createProgram();

            shaderInfo.forEach(function (desc) {
                let shader = compileShader(desc.id, desc.type);

                if (shader) {
                    gl.attachShader(program, shader);
                }
            });

            gl.linkProgram(program)

            if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
                console.log("Error linking shader program:");
                console.log(gl.getProgramInfoLog(program));
            }

            return program;
        }

        function compileShader(id, type) {
            let code = document.getElementById(id).firstChild.nodeValue;
            let shader = gl.createShader(type);

            gl.shaderSource(shader, code);
            gl.compileShader(shader);

            if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
                console.log(`Error compiling ${type === gl.VERTEX_SHADER ? "vertex" : "fragment"} shader:`);
                console.log(gl.getShaderInfoLog(shader));
            }
            return shader;
        }

        function animateScene(currTime) {

            let elapsed = (currTime - prevTime) / 1000.0;
            prevTime = currTime;

            for (var i = 0; i < flareCount; i++) {

                flarePos[i][0] += flareVel[i][0] * elapsed;
                flarePos[i][1] += flareVel[i][1] * elapsed;

                if (flarePos[i][0] < -buffer) {
                    flarePos[i][0] = -buffer;
                    flareVel[i][0] = -flareVel[i][0];
                } else if (flarePos[i][0] > windowWidth + buffer) {
                    flarePos[i][0] = windowWidth + buffer;
                    flareVel[i][0] = -flareVel[i][0];
                }

                if (flarePos[i][1] < -buffer) {
                    flarePos[i][1] = -buffer;
                    flareVel[i][1] = -flareVel[i][1];
                } else if (flarePos[i][1] > windowHeight + buffer) {
                    flarePos[i][1] = windowHeight + buffer;
                    flareVel[i][1] = -flareVel[i][1];
                }
            }

            for (var i = 0; i < flareCount - 1; i++) {

                for (var j = i + 1; j < flareCount; j++) {
                    let diffPos = [flarePos[i][0] - flarePos[j][0], flarePos[i][1] - flarePos[j][1]];
                    let distance = Math.pow(diffPos[0] * diffPos[0] + diffPos[1] * diffPos[1], 0.5);

                    if (distance < flareRad * 2) {
                        if (!flareCol[i][j]) {
                            let diffVel = [flareVel[i][0] - flareVel[j][0], flareVel[i][1] - flareVel[j][1]];
                            let normal = [-diffPos[0] / distance, -diffPos[1] / distance];
                            let dot = normal[0] * diffVel[0] + normal[1] * diffVel[1];
                            let bVel = [normal[0] * dot, normal[1] * dot];
                            let aVel = [diffVel[0] - bVel[0], diffVel[1] - bVel[1]];

                            flareVel[i][0] = aVel[0] + flareVel[j][0];
                            flareVel[i][1] = aVel[1] + flareVel[j][1];

                            flareVel[j][0] = bVel[0] + flareVel[j][0];
                            flareVel[j][1] = bVel[1] + flareVel[j][1];

                            flareCol[i][j] = true;
                        }
                    } else {
                        flareCol[i][j] = false;
                    }
                }
            }

            gl.uniform2fv(uPoint0, flarePos[0]);
            gl.uniform2fv(uPoint1, flarePos[1]);
            gl.uniform2fv(uPoint2, flarePos[2]);
            gl.uniform2fv(uPoint3, flarePos[3]);
            gl.uniform2fv(uPoint4, flarePos[4]);
            //   gl.uniform2fv(uPoint5, flarePos[5]);
            //   gl.uniform2fv(uPoint6, flarePos[6]);
            //   gl.uniform2fv(uPoint7, flarePos[7]);
            
            gl.drawArrays(gl.TRIANGLE_STRIP, 0, vertexCount);

            window.requestAnimationFrame(animateScene);
        }

        startup();
        window.requestAnimationFrame(animateScene);



// Fill the buffer with the values that define a letter 'F'.


// tmp = bias / (length(gl_FragCoord.xy - uPoint0) + 0.1);
//             tmp = (tmp > 1.0) ? 1.0 : tmp;
//             shift += tmp ;

             //tmp = 1.0 - ((length(gl_FragCoord.xy - uPoint1) + 50.0) / bias);
                //if(tmp > 0.0){
                    //shift += tmp*tmp;
                //}     

    </script>
    <script id="fragment-shader" type="x-shader/x-fragment">
        #ifdef GL_ES
          precision highp float;
        #endif
      
        uniform vec4 uColorBase;
        uniform vec4 uColorPoint;

        uniform float uDeviation;

        uniform vec2 uPoint0;
        uniform vec2 uPoint1;
        uniform vec2 uPoint2;
        uniform vec2 uPoint3;
        uniform vec2 uPoint4;
        uniform vec2 uPoint5;
        uniform vec2 uPoint6;
        uniform vec2 uPoint7;
      
        void main() {

            float total = 0.0;
            float e = 2.71828;
            vec2 diff;
            float length2;
            float amplitude = 0.65;
            float intensity;

            diff = gl_FragCoord.xy - uPoint0;
            length2 = (diff[0]*diff[0]) + (diff[1]*diff[1]);
            intensity = amplitude * pow(e, (-length2 / uDeviation));
            total = 1.0 - ((1.0-total) * (1.0-intensity));

            diff = gl_FragCoord.xy - uPoint1;
            length2 = (diff[0]*diff[0]) + (diff[1]*diff[1]);
            intensity = amplitude * pow(e, (-length2 / uDeviation));
            total = 1.0 - ((1.0-total) * (1.0-intensity));

            diff = gl_FragCoord.xy - uPoint2;
            length2 = (diff[0]*diff[0]) + (diff[1]*diff[1]);
            intensity = amplitude * pow(e, (-length2 / uDeviation));
            total = 1.0 - ((1.0-total) * (1.0-intensity));

            diff = gl_FragCoord.xy - uPoint3;
            length2 = (diff[0]*diff[0]) + (diff[1]*diff[1]);
            intensity = amplitude * pow(e, (-length2 / uDeviation));
            total = 1.0 - ((1.0-total) * (1.0-intensity));

            diff = gl_FragCoord.xy - uPoint4;
            length2 = (diff[0]*diff[0]) + (diff[1]*diff[1]);
            intensity = amplitude * pow(e, (-length2 / uDeviation));
            total = 1.0 - ((1.0-total) * (1.0-intensity));

            


            if(total > 1.0){
                total = 1.0;
            }

            gl_FragColor = ((uColorPoint - uColorBase) * total) + uColorBase;
          
        }
      </script>

    <script id="vertex-shader" type="x-shader/x-vertex">
        attribute vec2 aVertexPosition;
      
        uniform vec2 uScalingFactor;
      
        void main() {
          gl_Position = vec4(aVertexPosition * uScalingFactor, 0.0, 1.0);
        }
      </script>